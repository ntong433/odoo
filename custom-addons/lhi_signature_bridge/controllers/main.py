import hashlib
import hmac
import json

from odoo import http
from odoo.http import request


class OpenSignController(http.Controller):
    @http.route(
        "/api/opensign/callback",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def opensign_callback(self):
        raw_payload = request.httprequest.get_data(cache=True, as_text=False)
        if not raw_payload or len(raw_payload) > 200000:
            return request.make_json_response(
                {"status": "error", "message": "Invalid payload"}, status=400
            )
        try:
            payload = json.loads(raw_payload)
        except (TypeError, ValueError):
            return request.make_json_response(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )
        provider_id = payload.get("objectId") or payload.get("document_id")
        if not provider_id or not payload.get("event"):
            return request.make_json_response(
                {"status": "error", "message": "Missing event identity"}, status=400
            )
        signature_requests = (
            request.env["lhi.opensign.request"]
            .sudo()
            .search([("provider_request_id", "=", provider_id)])
        )
        if not signature_requests:
            return request.make_json_response(
                {"status": "error", "message": "Request not found"}, status=404
            )
        received = request.httprequest.headers.get("x-webhook-signature", "")
        authenticated = request.env["lhi.opensign.request"]
        configured = False
        for signature_request in signature_requests.filtered("configuration_id"):
            try:
                secret = signature_request.configuration_id.webhook_secret()
            except Exception:
                continue
            configured = True
            expected = hmac.new(
                secret.encode(), raw_payload, hashlib.sha256
            ).hexdigest()
            if received and hmac.compare_digest(received.strip().lower(), expected):
                authenticated |= signature_request
        if not configured:
            return request.make_json_response(
                {"status": "error", "message": "Webhook not configured"}, status=503
            )
        if len(authenticated) != 1:
            return request.make_json_response(
                {"status": "error", "message": "Invalid signature"}, status=401
            )
        signature_request = authenticated
        try:
            event, duplicate = (
                request.env["lhi.opensign.webhook.event"]
                .sudo()
                .receive(signature_request, payload, raw_payload)
            )
        except Exception:
            return request.make_json_response(
                {"status": "error", "message": "Event validation failed"}, status=409
            )
        if event.state == "failed":
            return request.make_json_response(
                {"status": "error", "message": "Event processing failed"}, status=503
            )
        return request.make_json_response(
            {"status": "duplicate" if duplicate else "success"}, status=200
        )
