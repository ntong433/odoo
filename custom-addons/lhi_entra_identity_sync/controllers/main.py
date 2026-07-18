import ipaddress
import logging
import os
import time
from urllib.parse import quote

from odoo import http, _
from odoo.http import request

from odoo.addons.auth_oauth.controllers.main import OAuthLogin

_logger = logging.getLogger(__name__)

MAINTENANCE_SESSION_KEY = "lhi_entra_maintenance_until"


class LhiEntraLoginController(OAuthLogin):
    def list_providers(self):
        providers = super().list_providers()
        valid_providers = []

        canonical_provider = request.env.ref(
            "lhi_entra_identity_sync.oauth_provider_microsoft_entra", raise_if_not_found=False
        )
        expected_client = "02b3748f-e84b-4bec-935a-21fab1498517"
        expected_endpoint = (
            "https://login.microsoftonline.com/552a1d00-ce70-4fdb-940f-0ad131e4b9cb/oauth2/v2.0/authorize"
        )

        for p in providers:
            is_canonical = canonical_provider and p.get("id") == canonical_provider.id
            client_id = str(p.get("client_id") or "").strip()

            if not is_canonical and client_id != expected_client:
                _logger.debug("Provider rejection: not canonical provider and client ID mismatch.")
                continue

            if not client_id:
                _logger.debug("Provider rejection: client ID present but empty.")
                continue

            if "PLACEHOLDER" in client_id.upper():
                _logger.debug("Provider rejection: client ID placeholder detected.")
                continue

            if client_id != expected_client:
                _logger.debug("Provider rejection: client ID does not match expected value.")
                continue

            auth_endpoint = str(p.get("auth_endpoint") or "").strip().rstrip("/")
            if auth_endpoint != expected_endpoint:
                _logger.debug("Provider rejection: tenant endpoint matched failed. Expected %s, got %s", expected_endpoint, auth_endpoint)
                continue

            if not p.get("auth_link"):
                _logger.debug("Provider rejection: auth_link not generated.")
                continue

            _logger.debug("Canonical XML ID resolved and provider validation passed.")
            valid_providers.append(p)

        return valid_providers

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

    @http.route()
    def web_login(self, redirect=None, **kwargs):
        # Preserve the custom LHI dashboard only as the authenticated user's landing action
        redirect = redirect or request.params.get("redirect") or "/odoo"
        response = super().web_login(redirect=redirect, **kwargs)

        if request.httprequest.method == "POST" and request.session.uid:
            user = request.env["res.users"].sudo().browse(request.session.uid)
            if user.lhi_local_maintenance_admin and not (
                self._maintenance_session_active()
                and self._maintenance_source_allowed()
            ):
                request.session.logout(keep_db=True)
                return request.make_response(
                    _("Protected maintenance login is not available from this route."),
                    status=403,
                )
            if user.lhi_local_maintenance_admin:
                request.env["lhi.audit.log"].create_event(
                    event_type="maintenance_login",
                    res_model="res.users",
                    res_id=user.id,
                    description=_("Protected local maintenance administrator login succeeded."),
                )
                request.session.pop(MAINTENANCE_SESSION_KEY, None)
        return response
