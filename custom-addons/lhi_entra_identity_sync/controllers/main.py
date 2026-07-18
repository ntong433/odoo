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
        _logger.info(f"Odoo native list_providers returned: {providers}")
        return providers

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
