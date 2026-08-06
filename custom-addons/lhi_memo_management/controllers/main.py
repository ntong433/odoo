from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import redirect

from odoo import http
from odoo.http import request


class LhiMemoProviderController(http.Controller):
    @staticmethod
    def _memo(memo_uuid):
        memo = request.env["lhi.memo"].search([("uuid", "=", memo_uuid)], limit=1)
        if not memo:
            raise NotFound()
        return memo

    @http.route(
        "/lhi/memo/<string:memo_uuid>/prepare",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=True,
    )
    def open_preparation(self, memo_uuid, **kwargs):
        memo = self._memo(memo_uuid)
        try:
            memo._ensure_requester_or_preparer()
        except Exception as error:
            raise Forbidden(str(error)) from error
        signature_request = memo.signature_request_id.sudo()
        url = signature_request.provider_preparation_url
        if not url or not signature_request.configuration_id:
            raise NotFound()
        signature_request.configuration_id._validated_url(url, purpose="redirect")
        return redirect(url, code=303)

    @http.route(
        "/lhi/memo/<string:memo_uuid>/participant",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=True,
    )
    def open_participant_action(self, memo_uuid, **kwargs):
        memo = self._memo(memo_uuid)
        try:
            signature_request = memo.sudo().signature_request_id
            url = signature_request.sudo().signing_url_for_user(
                request.env.user
            )
        except Exception as error:
            raise Forbidden(str(error)) from error
        return redirect(url, code=303)
