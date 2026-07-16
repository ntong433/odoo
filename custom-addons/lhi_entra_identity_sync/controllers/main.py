import ipaddress
import os
import time
from urllib.parse import quote

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
