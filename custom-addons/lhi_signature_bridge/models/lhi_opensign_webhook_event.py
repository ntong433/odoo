import hashlib
import json
from datetime import datetime, timezone

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LhiOpenSignWebhookEvent(models.Model):
    _name = "lhi.opensign.webhook.event"
    _description = "LHI Sign Webhook Event"
    _order = "received_at desc, id desc"

    provider_event_id = fields.Char(required=True, readonly=True, index=True)
    request_id = fields.Many2one(
        "lhi.opensign.request",
        required=True,
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, index=True
    )
    event_type = fields.Char(required=True, readonly=True, index=True)
    payload_digest = fields.Char(required=True, readonly=True, index=True)
    raw_payload = fields.Text(
        readonly=True, groups="lhi_signature_bridge.group_lhi_signature_admin"
    )
    provider_timestamp = fields.Datetime(readonly=True)
    received_at = fields.Datetime(
        default=fields.Datetime.now, required=True, readonly=True
    )
    processed_at = fields.Datetime(readonly=True)
    state = fields.Selection(
        [
            ("received", "Received"),
            ("processed", "Processed"),
            ("ignored", "Ignored"),
            ("failed", "Failed"),
        ],
        default="received",
        required=True,
        readonly=True,
        index=True,
    )
    safe_message = fields.Text(readonly=True)

    _provider_event_unique = models.Constraint(
        "unique(provider_event_id)", "The provider webhook event was already received."
    )

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @api.model
    def _event_identity(self, signature_request, payload, payload_digest):
        event_type = (payload.get("event") or "unknown").strip().lower()
        explicit = payload.get("eventId") or payload.get("event_id")
        if explicit:
            return f"opensign:{signature_request.configuration_id.id}:{explicit}"
        signer = payload.get("signer") or {}
        timestamp = (
            payload.get("signedAt")
            or payload.get("viewedAt")
            or payload.get("completedAt")
            or payload.get("declinedAt")
            or payload.get("createdAt")
            or ""
        )
        stable = "|".join(
            [
                str(signature_request.configuration_id.id),
                signature_request.provider_request_id or "",
                event_type,
                str(timestamp),
                (
                    signer.get("email")
                    or payload.get("viewedBy")
                    or payload.get("declinedBy")
                    or ""
                ).lower(),
                payload_digest,
            ]
        )
        return f"opensign:{hashlib.sha256(stable.encode()).hexdigest()}"

    @api.model
    def receive(self, signature_request, payload, raw_payload):
        payload_digest = hashlib.sha256(raw_payload).hexdigest()
        provider_event_id = self._event_identity(
            signature_request, payload, payload_digest
        )
        existing = self.sudo().search(
            [("provider_event_id", "=", provider_event_id)], limit=1
        )
        if existing:
            if existing.payload_digest != payload_digest:
                raise ValidationError(
                    _("A provider event ID was replayed with a different payload.")
                )
            # Provider retries are the recovery mechanism for a transient local
            # storage failure.  Re-run only a previously failed event; processed
            # and ignored events remain strict no-ops.
            if existing.state == "failed":
                existing.sudo().write({"state": "received", "safe_message": False})
                try:
                    if (payload.get("event") or "").strip().lower() == "completed":
                        signature_request.process_provider_event(existing, payload)
                    else:
                        with self.env.cr.savepoint():
                            signature_request.process_provider_event(existing, payload)
                    if existing.state == "received":
                        existing.sudo().write(
                            {
                                "state": "processed",
                                "processed_at": fields.Datetime.now(),
                            }
                        )
                except Exception as error:
                    existing.sudo().write(
                        {"state": "failed", "safe_message": str(error)[:2000]}
                    )
            return existing, True
        event_type = (payload.get("event") or "unknown").strip().lower()
        provider_timestamp = self._parse_datetime(
            payload.get("signedAt")
            or payload.get("viewedAt")
            or payload.get("completedAt")
            or payload.get("declinedAt")
            or payload.get("createdAt")
        )
        try:
            with self.env.cr.savepoint():
                event = self.sudo().create(
                    {
                        "provider_event_id": provider_event_id,
                        "request_id": signature_request.id,
                        "event_type": event_type,
                        "payload_digest": payload_digest,
                        "raw_payload": raw_payload.decode("utf-8", errors="replace")[
                            :200000
                        ],
                        "provider_timestamp": provider_timestamp,
                    }
                )
        except IntegrityError:
            # A concurrent delivery won the unique-key race. Do not recurse
            # using this transaction because its snapshot may not yet expose
            # the row committed by the winning request. The controller treats
            # an empty duplicate result as an acknowledged concurrent replay.
            return self.browse(), True
        try:
            if event_type == "completed":
                signature_request.process_provider_event(event, payload)
            else:
                with self.env.cr.savepoint():
                    signature_request.process_provider_event(event, payload)
            if event.state == "received":
                event.sudo().write(
                    {"state": "processed", "processed_at": fields.Datetime.now()}
                )
        except Exception as error:
            event.sudo().write({"state": "failed", "safe_message": str(error)[:2000]})
        return event, False

    @api.model
    def create_reconciliation_event(self, signature_request, payload):
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(normalized).hexdigest()
        identity = hashlib.sha256(
            f"reconcile|{signature_request.id}|{digest}".encode()
        ).hexdigest()
        existing = self.sudo().search(
            [("provider_event_id", "=", f"reconcile:{identity}")], limit=1
        )
        if existing:
            return existing
        return self.sudo().create(
            {
                "provider_event_id": f"reconcile:{identity}",
                "request_id": signature_request.id,
                "event_type": "completed",
                "payload_digest": digest,
                "raw_payload": normalized.decode(),
            }
        )
