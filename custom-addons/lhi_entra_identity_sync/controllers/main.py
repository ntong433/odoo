import base64
import ipaddress
import json
import logging
import os
import time
from urllib.parse import quote, urlencode

import requests
import werkzeug

from odoo import http, _
from odoo.http import request

from odoo.addons.auth_oauth.controllers.main import OAuthLogin


MAINTENANCE_SESSION_KEY = "lhi_entra_maintenance_until"


class LhiEntraLoginController(OAuthLogin):
    @staticmethod
    def _client_ip():
        trust_proxy = os.environ.get(
            "LHI_ENTRA_TRUST_PROXY_HEADERS", ""
        ).strip().lower() in {"1", "true", "yes"}
        if trust_proxy:
            forwarded = request.httprequest.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return request.httprequest.remote_addr or ""

    @classmethod
    def _maintenance_source_allowed(cls):
        raw_networks = os.environ.get("LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS", "")
        if not raw_networks:
            return False
        try:
            address = ipaddress.ip_address(cls._client_ip())
        except ValueError:
            return False
        for raw_network in raw_networks.split(","):
            try:
                if address in ipaddress.ip_network(raw_network.strip(), strict=False):
                    return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _maintenance_session_active():
        return float(request.session.get(MAINTENANCE_SESSION_KEY) or 0) >= time.time()

    def _configuration(self):
        if not request.db:
            return request.env["lhi.entra.configuration"]
        return request.env["lhi.entra.configuration"].sudo()._get_for_company(
            required=False
        )

    def _provider_link(self, configuration, redirect=None):
        request.params["redirect"] = redirect or request.params.get("redirect") or "/odoo"
        providers = self.list_providers()
        provider = next(
            (
                item
                for item in providers
                if item["id"] == configuration.oauth_provider_id.id
            ),
            None,
        )
        return provider.get("auth_link") if provider else False

    @http.route(
        "/lhi/maintenance/login",
        type="http",
        auth="none",
        readonly=False,
        sitemap=False,
    )
    def maintenance_login(self, redirect="/odoo", **kwargs):
        if not self._maintenance_source_allowed():
            return request.not_found()
        request.session[MAINTENANCE_SESSION_KEY] = time.time() + 15 * 60
        return request.redirect(
            "/web/login?lhi_maintenance=1&redirect=%s"
            % quote(redirect or "/odoo", safe="")
        )

    @http.route(
        "/lhi/auth/microsoft/login",
        type="http",
        auth="none",
        readonly=False,
        sitemap=False,
    )
    def lhi_microsoft_login(self, **kwargs):
        configuration = self._configuration()
        if not configuration or not configuration.oauth_provider_id.enabled:
            return request.make_response(_("Microsoft Entra login is not configured."), status=503)

        provider = configuration.oauth_provider_id
        client_id = provider.client_id
        auth_endpoint = provider.auth_endpoint
        
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        redirect_uri = f"{base_url}/auth_oauth/signin"
        
        state = os.urandom(16).hex()
        nonce = os.urandom(16).hex()
        
        request.session['oauth_state'] = state
        request.session['oauth_nonce'] = nonce
        
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": provider.scope,
            "state": state,
            "nonce": nonce,
            "prompt": "select_account"
        }
        url = f"{auth_endpoint}?{urlencode(params)}"
        return request.redirect(url)

    @http.route('/auth_oauth/signin', type='http', auth='none')
    def signin(self, **kw):
        state = kw.get('state')
        code = kw.get('code')
        error = kw.get('error')
        error_description = kw.get('error_description', '')

        if error:
            _logger.error("OAuth error: %s - %s", error, error_description)
            return request.redirect('/web/login?oauth_error=1')
            
        if not code or not state:
            # Fall back to standard Odoo implicit flow if no code is provided
            return super().signin(**kw)
            
        # 1. Validate State
        stored_state = request.session.get('oauth_state')
        if not stored_state or state != stored_state:
            _logger.error("OAuth state mismatch or missing state.")
            return self._safe_error_response("Invalid OAuth state.")
            
        configuration = self._configuration()
        if not configuration:
            return self._safe_error_response("Entra configuration missing.")
            
        provider = configuration.oauth_provider_id
        client_id = provider.client_id
        client_secret = os.environ.get("ENTRA_CLIENT_SECRET")
        if not client_secret:
            _logger.error("ENTRA_CLIENT_SECRET is not configured.")
            return self._safe_error_response("Server configuration error.")
            
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        redirect_uri = f"{base_url}/auth_oauth/signin"
        
        # Determine token endpoint
        token_endpoint = provider.auth_endpoint.replace("/authorize", "/token")
        
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": provider.scope,
        }
        
        try:
            # 2. Exchange Code for Token
            token_response = requests.post(token_endpoint, data=token_data, timeout=15)
            token_response.raise_for_status()
            tokens = token_response.json()
            access_token = tokens.get('access_token')
            id_token = tokens.get('id_token')
            
            # 3. Validate ID Token
            if id_token:
                payload_b64 = id_token.split('.')[1]
                payload_b64 += '=' * (-len(payload_b64) % 4)
                id_token_payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
                
                tid = id_token_payload.get("tid")
                expected_tenant = os.environ.get("ENTRA_TENANT_ID")
                if expected_tenant and tid and tid != expected_tenant:
                    _logger.error("Invalid tenant ID: %s", tid)
                    return self._safe_error_response("Invalid tenant.")
                
                nonce_claim = id_token_payload.get("nonce")
                stored_nonce = request.session.get('oauth_nonce')
                if not stored_nonce or nonce_claim != stored_nonce:
                    _logger.error("Nonce mismatch.")
                    return self._safe_error_response("Invalid OAuth nonce.")
            
            # 4. Fetch User Info
            userinfo_endpoint = provider.validation_endpoint or "https://graph.microsoft.com/v1.0/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_resp = requests.get(userinfo_endpoint, headers=headers, timeout=15)
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
            
            validation = {
                "user_id": userinfo.get("id") or userinfo.get("oid") or userinfo.get("sub"),
                "userPrincipalName": userinfo.get("userPrincipalName") or userinfo.get("upn"),
                "mail": userinfo.get("mail") or userinfo.get("email"),
                "accountEnabled": userinfo.get("accountEnabled", True),
                "displayName": userinfo.get("displayName") or userinfo.get("name"),
            }
            
            request.session.pop('oauth_state', None)
            request.session.pop('oauth_nonce', None)
            
            dbname = request.db
            params_auth = {"access_token": access_token}
            
            # 5. Authenticate via Odoo
            user_login = request.env['res.users'].sudo()._auth_oauth_signin(provider.id, validation, params_auth)
            request.session.authenticate(dbname, user_login, access_token)
            
            # Trigger post-login sync if implemented
            user = request.env['res.users'].sudo().search([('login', '=', user_login)], limit=1)
            if user and hasattr(user, '_lhi_queue_entra_profile_sync'):
                user._lhi_queue_entra_profile_sync()
                
            return request.redirect('/web')
            
        except Exception as e:
            _logger.exception("OAuth code exchange or validation failed.")
            return self._safe_error_response("Microsoft sign-in could not be completed.")

    def _safe_error_response(self, message):
        error_id = os.urandom(4).hex().upper()
        _logger.error("OAuth Error Reference: %s", error_id)
        return request.make_response(
            f"{message}\nPlease contact the LHI IT Helpdesk with reference ID: {error_id}", 
            status=500
        )

    @http.route()
    def web_login(self, redirect=None, **kwargs):
        configuration = self._configuration()
        if not configuration or not configuration.primary_sso_enabled:
            return super().web_login(redirect=redirect, **kwargs)

        maintenance_active = (
            self._maintenance_session_active() and self._maintenance_source_allowed()
        )
        method = request.httprequest.method
        oauth_error = request.params.get("oauth_error")

        if method == "GET" and not request.session.uid and not maintenance_active:
            if oauth_error:
                return super().web_login(redirect=redirect, **kwargs)
            link = self._provider_link(configuration, redirect=redirect)
            if link:
                return request.redirect(link)
            return request.make_response(
                _("Microsoft Entra login is required but is not correctly configured."),
                status=503,
            )

        if method == "POST" and not maintenance_active:
            link = self._provider_link(configuration, redirect=redirect)
            return (
                request.redirect(link)
                if link
                else request.make_response(_("Microsoft Entra login is unavailable."), status=503)
            )

        response = super().web_login(redirect=redirect, **kwargs)
        if method == "POST" and request.session.uid:
            user = request.env["res.users"].sudo().browse(request.session.uid)
            if not user.lhi_local_maintenance_admin:
                request.session.logout(keep_db=True)
                return request.make_response(
                    _("This route accepts protected maintenance administrators only."),
                    status=403,
                )
            request.env["lhi.audit.log"].create_event(
                event_type="maintenance_login",
                res_model="res.users",
                res_id=user.id,
                description=_("Protected local maintenance administrator login succeeded."),
            )
            request.session.pop(MAINTENANCE_SESSION_KEY, None)
        return response
