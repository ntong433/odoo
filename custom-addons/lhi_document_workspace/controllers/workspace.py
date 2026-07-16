from html import escape
from urllib.parse import urlparse

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


class LhiDocumentWorkspaceController(http.Controller):
    @http.route(
        "/lhi/document-workspace/preview/<string:document_uuid>",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def preview_document(self, document_uuid, **kwargs):
        document = request.env["lhi.document.item"].sudo().search(
            [
                ("uuid", "=", document_uuid),
                ("active", "=", True),
                ("storage_policy_id.workspace_enabled", "=", True),
            ],
            limit=1,
        )
        if not document:
            return request.not_found()
        try:
            document.with_user(request.env.user).check_linked_access("read")
            if document.storage_state != "available":
                raise UserError(_("The document is unavailable."))
            payload = document._workspace_preview_payload(request.env.user)
            document.with_context(
                lhi_workspace_user_id=request.env.user.id
            )._workspace_audit(
                "document_preview",
                _("Previewed '%s' inside Odoo.") % document.name,
            )
            get_url = payload.get("getUrl")
            if get_url and urlparse(get_url).scheme == "https":
                return request.redirect(get_url, code=302, local=False)
            post_url = payload.get("postUrl")
            if post_url and urlparse(post_url).scheme == "https":
                inputs = "".join(
                    f'<input type="hidden" name="{escape(str(key))}" '
                    f'value="{escape(str(value))}"/>'
                    for key, value in (payload.get("postParameters") or {}).items()
                )
                html = (
                    "<!doctype html><html><body>"
                    f'<form id="preview" method="post" action="{escape(post_url)}">'
                    f"{inputs}</form><script>document.getElementById('preview').submit();"
                    "</script></body></html>"
                )
                return request.make_response(
                    html,
                    headers=[
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Cache-Control", "no-store"),
                        ("Referrer-Policy", "no-referrer"),
                    ],
                )
        except (AccessError, UserError, ValidationError):
            return request.not_found()
        return request.not_found()

    @http.route(
        "/lhi/document-workspace/version/confirm",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def confirm_version(self, document_uuid, item_id):
        document = request.env["lhi.document.item"].sudo().search(
            [
                ("uuid", "=", document_uuid),
                ("active", "=", True),
                ("storage_policy_id.workspace_enabled", "=", True),
                ("upload_state", "=", "session"),
            ],
            limit=1,
        )
        if not document:
            raise AccessError(_("The version upload session is invalid or expired."))
        return document.with_user(request.env.user)._workspace_confirm_version(item_id)
