import logging

from werkzeug.exceptions import BadRequest

from odoo import fields, http, tools
from odoo.http import request


_logger = logging.getLogger(__name__)


class LhiMicrosoftGraphOAuthController(http.Controller):
    @http.route(
        "/lhi/microsoft_graph/oauth/callback",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
        readonly=False,
    )
    def delegated_oauth_callback(self, **params):
        state_payload = params.get("state")
        if not state_payload:
            raise BadRequest("Missing OAuth state")
        try:
            state = tools.verify_hash_signed(
                request.env(su=True),
                "lhi-microsoft-graph-delegated",
                state_payload,
            )
        except (TypeError, ValueError):
            state = None
        if (
            not state
            or state.get("db") != request.env.cr.dbname
            or state.get("user_id") != request.env.user.id
        ):
            raise BadRequest("Invalid OAuth state")
        oauth_state = request.env["lhi.graph.oauth.state"].sudo().browse(
            state.get("state_id")
        )
        if (
            not oauth_state.exists()
            or oauth_state.used
            or oauth_state.nonce != state.get("nonce")
            or oauth_state.user_id != request.env.user
            or oauth_state.expires_at <= fields.Datetime.now()
        ):
            raise BadRequest("Expired or reused OAuth state")
        if params.get("error"):
            oauth_state.used = True
            _logger.warning(
                "Delegated Microsoft Graph authorization failed for user ID %s: %s",
                request.env.user.id,
                oauth_state.connection_id._redact_text(params.get("error")),
            )
            return request.redirect("/odoo", 303)
        code = params.get("code")
        if not code:
            raise BadRequest("Missing authorization code")
        redirect_uri = oauth_state.connection_id._delegated_redirect_uri()
        try:
            with request.env.cr.savepoint():
                oauth_state.connection_id.exchange_delegated_code(
                    code,
                    redirect_uri,
                    oauth_state.code_verifier,
                    request.env.user,
                )
            oauth_state.used = True
        except Exception:
            oauth_state.used = True
            _logger.exception(
                "Delegated Microsoft Graph token exchange failed for user ID %s",
                request.env.user.id,
            )
        return request.redirect("/odoo", 303)
