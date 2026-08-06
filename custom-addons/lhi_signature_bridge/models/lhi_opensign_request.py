import base64
import hashlib
import logging
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"completed", "cancelled", "declined", "expired", "superseded"}


class LhiOpenSignRequest(models.Model):
    _name = "lhi.opensign.request"
    _description = "LHI OpenSign Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    MEMO_SIGNATURE_CONTRACT_VERSION = 1

    name = fields.Char(
        string="Request Reference", required=True, copy=False, default="New", index=True
    )
    res_model = fields.Char(
        string="Resource Model", required=True, readonly=True, index=True
    )
    res_id = fields.Integer(
        string="Resource ID", required=True, readonly=True, index=True
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
    )

    source_pdf = fields.Binary(string="Source PDF Document")
    source_pdf_name = fields.Char(default="source.pdf")
    source_pdf_hash = fields.Char(
        string="Source PDF Hash", readonly=True, tracking=True
    )

    signatories = fields.Text(string="Signatories (JSON)", required=True, default="{}")
    recipient_ids = fields.One2many(
        "lhi.opensign.recipient", "request_id", string="Recipients", copy=False
    )
    sequence_type = fields.Selection(
        [("sequential", "Sequential"), ("parallel", "Parallel")],
        string="Routing Sequence",
        default="sequential",
        required=True,
    )

    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("preparing", "Preparing"),
            ("requester_signature_pending", "Requester Signature Pending"),
            ("sent", "Sent"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("declined", "Declined"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("failed", "Failed"),
            ("superseded", "Superseded"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    expiry_date = fields.Datetime(string="Expiry Date")

    configuration_id = fields.Many2one(
        "lhi.opensign.configuration", readonly=True, ondelete="restrict", index=True
    )
    idempotency_key = fields.Char(readonly=True, copy=False, index=True)
    provider_request_id = fields.Char(readonly=True, copy=False, index=True)
    provider_status = fields.Char(readonly=True, tracking=True)
    provider_preparation_url = fields.Char(
        readonly=True, groups="lhi_signature_bridge.group_lhi_signature_admin"
    )
    preparation_completed = fields.Boolean(readonly=True)
    provider_creation_uncertain = fields.Boolean(readonly=True)
    current_recipient_id = fields.Many2one(
        "lhi.opensign.recipient", readonly=True, copy=False
    )
    last_sync_at = fields.Datetime(readonly=True)
    supersedes_request_id = fields.Many2one(
        "lhi.opensign.request", readonly=True, copy=False, ondelete="restrict"
    )
    superseded_by_request_id = fields.Many2one(
        "lhi.opensign.request", readonly=True, copy=False, ondelete="restrict"
    )

    signed_pdf = fields.Binary(string="Signed PDF Document")
    signed_pdf_hash = fields.Char(string="Signed PDF Hash", readonly=True)
    audit_certificate = fields.Binary(string="Audit Certificate")
    source_document_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    signed_document_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    certificate_document_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    source_stored = fields.Boolean(compute="_compute_storage_flags")
    signed_stored = fields.Boolean(compute="_compute_storage_flags")
    certificate_stored = fields.Boolean(compute="_compute_storage_flags")

    callback_logs = fields.Text(
        string="Callback Logs", groups="lhi_signature_bridge.group_lhi_signature_admin"
    )
    retry_count = fields.Integer(string="Retry Count", default=0, readonly=True)
    error_message = fields.Text(string="Last Error Message", readonly=True)

    _idempotency_unique = models.Constraint(
        "unique(idempotency_key)", "The signature idempotency key must be unique."
    )
    _provider_request_unique = models.Constraint(
        "unique(configuration_id, provider_request_id)",
        "The provider request is already linked to Odoo.",
    )

    @api.constrains(
        "res_model", "res_id", "sequence_type", "company_id", "configuration_id"
    )
    def _check_source(self):
        for signature_request in self:
            if signature_request.res_id <= 0:
                raise ValidationError(
                    _("The source record identifier must be positive.")
                )
            if signature_request.res_model not in self.env.registry:
                if self.env.context.get("lhi_signature_company_backfill"):
                    continue
                raise ValidationError(_("The source model is not available."))
            if signature_request.sequence_type != "sequential":
                raise ValidationError(
                    _("LHI signature requests must use sequential routing.")
                )
            source = signature_request._source_record()
            if (
                source
                and "company_id" in source._fields
                and source.company_id
                and source.company_id != signature_request.company_id
            ):
                raise ValidationError(
                    _(
                        "The signature request and source must belong to the same company."
                    )
                )
            if (
                signature_request.configuration_id
                and signature_request.configuration_id.company_id
                != signature_request.company_id
            ):
                raise ValidationError(
                    _(
                        "The signature provider configuration belongs to another company."
                    )
                )

    @api.depends(
        "source_document_item_id",
        "signed_document_item_id",
        "certificate_document_item_id",
    )
    def _compute_storage_flags(self):
        for signature_request in self:
            signature_request.source_stored = bool(
                signature_request.source_document_item_id
                and signature_request.source_document_item_id.storage_state
                == "available"
            )
            signature_request.signed_stored = bool(
                signature_request.signed_document_item_id
                and signature_request.signed_document_item_id.storage_state
                == "available"
            )
            signature_request.certificate_stored = bool(
                signature_request.certificate_document_item_id
                and signature_request.certificate_document_item_id.storage_state
                == "available"
            )

    def _source_record(self):
        self.ensure_one()
        if self.res_model not in self.env.registry:
            return False
        return self.env[self.res_model].browse(self.res_id).exists()

    def _artifact_storage_target(self, field_name, suffix):
        self.ensure_one()
        source = self._source_record()
        if source and hasattr(source, "_lhi_opensign_storage_target"):
            target = source._lhi_opensign_storage_target(field_name, suffix)
            if target:
                return target
        return {
            "linked_model": self._name,
            "linked_record_id": self.id,
            "linked_field": field_name,
            "requested_by": self.env.user,
            "name": f"{self.name}-{suffix}.pdf",
        }

    def _store_sharepoint_binary(self, field_name, value, target_field, suffix):
        content = self.env["lhi.document.item"]._decode_binary_value(value)
        if not content:
            return
        for signature_request in self:
            target = signature_request._artifact_storage_target(field_name, suffix)
            item = self.env["lhi.document.item"].create_from_bytes(
                name=target["name"],
                content=content,
                mime_type="application/pdf",
                linked_model=target["linked_model"],
                linked_record_id=target["linked_record_id"],
                linked_field=target.get("linked_field"),
                requested_by=target.get("requested_by") or self.env.user,
                synchronous=True,
            )
            super(
                LhiOpenSignRequest,
                signature_request.with_context(lhi_sharepoint_opensign_skip=True),
            ).write({field_name: False, target_field: item.id})

    @api.model_create_multi
    def create(self, vals_list):
        payloads = [
            {
                name: values.get(name)
                for name in ("source_pdf", "signed_pdf", "audit_certificate")
            }
            for values in vals_list
        ]
        for vals in vals_list:
            # Business-document bytes belong in SharePoint.  Keep the inbound
            # payload in process memory until the synchronous upload confirms
            # its immutable DriveItem ID; never write it into an Odoo binary
            # column, including on a handled upload failure.
            for field_name in ("source_pdf", "signed_pdf", "audit_certificate"):
                vals.pop(field_name, None)
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("lhi.opensign.request")
                    or "OS-New"
                )
        records = super(
            LhiOpenSignRequest,
            self.with_context(lhi_sharepoint_skip_adapter=True),
        ).create(vals_list)
        for signature_request, payload in zip(records, payloads):
            signature_request._store_sharepoint_binary(
                "source_pdf",
                payload.get("source_pdf"),
                "source_document_item_id",
                "source",
            )
            signature_request._store_sharepoint_binary(
                "signed_pdf",
                payload.get("signed_pdf"),
                "signed_document_item_id",
                "signed",
            )
            signature_request._store_sharepoint_binary(
                "audit_certificate",
                payload.get("audit_certificate"),
                "certificate_document_item_id",
                "certificate",
            )
        return records

    def write(self, vals):
        if self.env.context.get("lhi_sharepoint_opensign_skip"):
            return super().write(vals)
        if {"res_model", "res_id"}.intersection(vals):
            for signature_request in self:
                if (
                    signature_request.provider_request_id
                    or signature_request.status != "draft"
                ):
                    raise ValidationError(
                        _(
                            "The signature source cannot change after provider processing starts."
                        )
                    )
        payloads = {
            name: vals.get(name)
            for name in ("source_pdf", "signed_pdf", "audit_certificate")
            if vals.get(name)
        }
        stored_vals = dict(vals)
        for field_name in payloads:
            stored_vals.pop(field_name, None)
        result = super(
            LhiOpenSignRequest,
            self.with_context(lhi_sharepoint_skip_adapter=True),
        ).write(stored_vals)
        mapping = {
            "source_pdf": ("source_document_item_id", "source"),
            "signed_pdf": ("signed_document_item_id", "signed"),
            "audit_certificate": ("certificate_document_item_id", "certificate"),
        }
        for field_name, value in payloads.items():
            target_field, suffix = mapping[field_name]
            self._store_sharepoint_binary(field_name, value, target_field, suffix)
        return result

    def _document_download_action(self, document):
        self.ensure_one()
        if not document:
            raise UserError(_("The requested document is not available."))
        document.with_user(self.env.user).check_linked_access("read")
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/sharepoint/document/{document.uuid}/download",
            "target": "new",
        }

    def action_download_source_document(self):
        self.ensure_one()
        return self._document_download_action(self.source_document_item_id.sudo())

    def action_download_signed_document(self):
        self.ensure_one()
        return self._document_download_action(self.signed_document_item_id.sudo())

    def action_download_audit_certificate(self):
        self.ensure_one()
        return self._document_download_action(self.certificate_document_item_id.sudo())

    def _lhi_source_pdf_bytes(self):
        self.ensure_one()
        if self.source_document_item_id:
            return self.source_document_item_id.download_bytes(
                auth_context="application"
            )
        return self.env["lhi.document.item"]._decode_binary_value(self.source_pdf)

    def _provider_signers(self):
        self.ensure_one()
        return [
            {
                "name": recipient.name,
                "email": recipient.email,
                "order": index,
                "role": "signer",
                "otp_required": not bool(recipient.entra_object_id),
            }
            for index, recipient in enumerate(
                self.recipient_ids.sudo().sorted("sequence"), start=1
            )
        ]

    def action_create_provider_draft(self, redirect_url=False):
        self.ensure_one()
        locked = self.try_lock_for_update()
        if not locked:
            raise UserError(
                _("This signature request is already being prepared. Please wait.")
            )
        self.invalidate_recordset(
            ["provider_request_id", "provider_creation_uncertain", "status"]
        )
        if self.provider_request_id:
            return self.provider_preparation_url
        if self.provider_creation_uncertain:
            raise UserError(
                _(
                    "The prior provider creation outcome is unknown. A signature "
                    "administrator must reconcile it before retrying."
                )
            )
        if not self.source_stored:
            raise UserError(
                _(
                    "The source PDF is not confirmed in SharePoint, so dispatch is blocked."
                )
            )
        if not self.recipient_ids:
            raise UserError(_("At least one controlled recipient is required."))
        emails = [email.strip().lower() for email in self.recipient_ids.mapped("email")]
        if len(emails) != len(set(emails)):
            raise UserError(
                _("A person cannot occupy two positions in one signature route.")
            )
        source = self._source_record()
        source_company = (
            source.company_id
            if source and "company_id" in source._fields and source.company_id
            else self.env.company
        )
        configuration = self.configuration_id or self.env[
            "lhi.opensign.configuration"
        ].active_for_company(source_company)
        source = self._lhi_source_pdf_bytes()
        payload = {
            "name": self.name,
            "description": self.name,
            "note": _(
                "LHI controlled memo approval and signature workflow."
            ),
            "mode": "draft",
            "file": {
                "name": f"{self.name.replace('/', '-')}.pdf",
                "content_type": "application/pdf",
                "base64": base64.b64encode(source).decode(),
            },
            "signers": self._provider_signers(),
            "send_in_order": True,
            "send_email": True,
            "integration": {
                "source": "lhi_erp",
                "model": self._name,
                "record_id": str(self.id),
                "reference": self.name,
            },
        }

        if self.expiry_date:
            expiry_value = self.expiry_date
            if hasattr(expiry_value, "date"):
                expiry_value = expiry_value.date()
            payload["expiration_date"] = fields.Date.to_string(
                expiry_value
            )

        if redirect_url:
            payload["redirect_url"] = redirect_url

        idempotency_key = (
            self.idempotency_key
            or (
                f"lhi-erp-signature-{self.id}-"
                f"{self.source_pdf_hash or 'no-hash'}"
            )
        )[:200]

        self.sudo().write({"configuration_id": configuration.id, "status": "preparing"})
        try:
            response = configuration.api_request(
                "POST",
                "/signature-requests",
                json_body=payload,
                retry_safe=False,
                idempotency_key=idempotency_key,
            )
        except UserError as error:
            self.sudo().write(
                {
                    "status": "failed",
                    "provider_creation_uncertain": "outcome is unknown"
                    in str(error).lower(),
                    "error_message": str(error),
                    "retry_count": self.retry_count + 1,
                }
            )
            raise
        provider_id = response.get("document_id") or response.get("objectId")
        if not provider_id:
            self.sudo().write(
                {
                    "status": "failed",
                    "provider_creation_uncertain": True,
                    "error_message": _(
                        "LHI Sign did not return a document ID and preparation URL."
                    ),
                }
            )
            raise UserError(_("LHI Sign returned an incomplete draft response."))
        encoded_doc_id = quote(str(provider_id))
        preparation_url = f"https://sign.lhinigeria.org/draftDocument?docId={encoded_doc_id}"
        configuration._validated_url(preparation_url, purpose="redirect")
        self.sudo().write(
            {
                "provider_request_id": provider_id,
                "provider_preparation_url": preparation_url,
                "provider_status": "draft",
                "status": "preparing",
                "provider_creation_uncertain": False,
                "last_sync_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        self.message_post(body=_("LHI Sign draft created for dynamic field placement."))
        return preparation_url

    @staticmethod
    def _normal_email(value):
        return (value or "").strip().lower()

    def _validate_required_widgets(self, payload):
        self.ensure_one()
        provider_signers = {
            self._normal_email(item.get("email")): item
            for item in payload.get("signers", [])
            if item.get("email")
        }
        missing = []
        for recipient in self.recipient_ids.filtered(
            lambda item: item.required_widget_types
        ):
            signer = provider_signers.get(self._normal_email(recipient.email)) or {}
            widget_types = {
                (widget.get("type") or "").strip().lower()
                for widget in signer.get("widgets", [])
            }
            required = {
                value.strip().lower()
                for value in recipient.required_widget_types.split(",")
                if value.strip()
            }
            absent = required - widget_types
            if absent:
                missing.append(f"{recipient.name}: {', '.join(sorted(absent))}")
        if missing:
            raise UserError(
                _("Required LHI Sign fields are missing: %s") % "; ".join(missing)
            )
        return True

    def provider_status_payload(self):
        self.ensure_one()
        if not self.provider_request_id or not self.configuration_id:
            raise UserError(_("No provider request is available to refresh."))
        payload = self.configuration_id.api_request(
            "GET", f"/signature-requests/{quote(self.provider_request_id)}", retry_safe=True
        )
        if (
            payload.get("objectId")
            and payload.get("objectId") != self.provider_request_id
        ):
            raise UserError(_("LHI Sign returned a different document identifier."))
        self.sudo().write(
            {
                "provider_status": payload.get("status") or self.provider_status,
                "last_sync_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        return payload

    def action_confirm_preparation(self):
        self.ensure_one()
        if self.status not in ("preparing", "failed"):
            raise UserError(_("This request is not awaiting field preparation."))
        payload = self.provider_status_payload()
        self._validate_required_widgets(payload)
        first = self.recipient_ids.sorted("sequence")[:1]
        self.sudo().write(
            {
                "preparation_completed": True,
                "status": "requester_signature_pending",
                "current_recipient_id": first.id if first else False,
                "error_message": False,
            }
        )
        self.message_post(body=_("Dynamic signature field preparation was validated."))
        return True

    def action_reset_uncertain_creation(self):
        """Allow a protected administrator to retry only after provider review."""
        if not self.env.user.has_group(
            "lhi_signature_bridge.group_lhi_signature_admin"
        ):
            raise AccessError(
                _("Only a Signature Administrator may reset an uncertain draft.")
            )
        for signature_request in self:
            if (
                signature_request.status != "failed"
                or not signature_request.provider_creation_uncertain
                or signature_request.provider_request_id
            ):
                raise UserError(
                    _(
                        "Only an uncertain provider creation without a provider ID can be reset."
                    )
                )
            signature_request.sudo().write(
                {
                    "status": "draft",
                    "provider_creation_uncertain": False,
                    "error_message": False,
                }
            )
            signature_request.message_post(
                body=_(
                    "Uncertain provider creation reset by %s after manual provider review."
                )
                % self.env.user.name
            )
        return True

    @staticmethod
    def _find_signing_links(payload):
        links = []

        def visit(value):
            if isinstance(value, dict):
                email = value.get("email") or value.get("Email")
                url = (
                    value.get("url")
                    or value.get("signing_url")
                    or value.get("signingUrl")
                )
                if email and url:
                    links.append((email, url))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
        return links

    def signing_url_for_user(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        recipient = self.recipient_ids.filtered(lambda item: item.user_id == user)[:1]
        if not recipient:
            raise AccessError(_("You are not a participant in this signature request."))
        if recipient != self.current_recipient_id:
            raise AccessError(_("A preceding participant must act first."))
        user_entra_id = user._get_entra_object_id_for_memo_integration()
        if not user_entra_id or user_entra_id != recipient.entra_object_id:
            raise AccessError(
                _("Your immutable Microsoft Entra identity does not match.")
            )
        payload = self.configuration_id.api_request(
            "GET", f"/signature-requests/{quote(self.provider_request_id)}/signing-links", retry_safe=True
        )
        target = False
        for email, url in self._find_signing_links(payload):
            if self._normal_email(email) == self._normal_email(recipient.email):
                target = self.configuration_id._validated_url(url, purpose="redirect")
                break
        if not target:
            raise UserError(
                _("LHI Sign did not return your current secure action URL.")
            )
        recipient.sudo().write({"provider_signing_url": target})
        return target

    def action_send(self):
        """Legacy entry point retained for existing business integrations."""
        for signature_request in self:
            if not signature_request.source_stored:
                signature_request.sudo().write(
                    {
                        "status": "failed",
                        "error_message": _(
                            "The source document is not confirmed in SharePoint. "
                            "OpenSign transmission was blocked."
                        ),
                    }
                )
                continue
            if signature_request.recipient_ids:
                signature_request.action_create_provider_draft()
            else:
                signature_request.sudo().write(
                    {"status": "sent", "error_message": False}
                )
                signature_request.message_post(
                    body=_("Document released to the existing OpenSign transport.")
                )
        return True

    def action_cancel(self):
        for signature_request in self:
            if signature_request.status in TERMINAL_STATUSES:
                continue
            if (
                signature_request.provider_request_id
                and signature_request.configuration_id
            ):
                signature_request.configuration_id.api_request(
                    "POST",
                    f"/signature-requests/{quote(signature_request.provider_request_id)}",
                    retry_safe=True,
                )
            signature_request.sudo().write(
                {"status": "cancelled", "provider_status": "revoked"}
            )
            signature_request.message_post(body=_("LHI Sign request cancelled."))
        return True

    def action_supersede(self, replacement=False):
        for signature_request in self:
            if signature_request.status not in TERMINAL_STATUSES:
                # A replacement must not proceed while an older provider
                # envelope may still accept signatures. Cancellation failure is
                # therefore blocking, not a warning-only condition.
                signature_request.action_cancel()
            vals = {"status": "superseded"}
            if replacement:
                vals["superseded_by_request_id"] = replacement.id
            signature_request.sudo().write(vals)
        if replacement:
            replacement.sudo().write({"supersedes_request_id": self[:1].id})
        return True

    def action_notify_current_recipient(self):
        """Request an email for the currently active sequential recipient."""
        self.ensure_one()

        if (
            not self.provider_request_id
            or not self.configuration_id
            or not self.current_recipient_id
            or self.status in TERMINAL_STATUSES
        ):
            return False

        response = self.configuration_id.sudo().api_request(
            "POST",
            (
                f"/signature-requests/"
                f"{self.provider_request_id}/remind"
            ),
            json_body={},
            retry_safe=False,
        )

        self.message_post(
            body=_(
                "LHI Sign notification requested for the current "
                "sequential recipient."
            )
        )

        return response

    def _recipient_from_payload(self, payload):
        signer = payload.get("signer") or {}
        email = (
            signer.get("email") or payload.get("viewedBy") or payload.get("declinedBy")
        )
        return self.recipient_ids.filtered(
            lambda item: self._normal_email(item.email) == self._normal_email(email)
        )[:1]

    @staticmethod
    def _provider_signer_completed(signer):
        """Recognize only explicit provider completion indicators."""
        status = (
            str(
                signer.get("status")
                or signer.get("signerStatus")
                or signer.get("signer_status")
                or ""
            )
            .strip()
            .lower()
        )
        return bool(
            signer.get("isSigned") is True
            or signer.get("is_signed") is True
            or signer.get("signedAt")
            or signer.get("signed_at")
            or status in {"signed", "approved", "completed"}
        )

    def _reconcile_completed_recipients(self, payload):
        """Replay missed participant confirmations in strict route order.

        A provider completion response is authoritative only when it explicitly
        identifies every completed participant.  It must never silently skip a
        pending Odoo approval stage.
        """
        self.ensure_one()
        signers = payload.get("signers") or payload.get("recipients") or []
        by_email = {
            self._normal_email(item.get("email") or item.get("Email")): item
            for item in signers
            if isinstance(item, dict) and (item.get("email") or item.get("Email"))
        }
        for recipient in self.recipient_ids.sorted("sequence"):
            if recipient.status == "completed":
                continue
            signer = by_email.get(self._normal_email(recipient.email))
            if not signer or not self._provider_signer_completed(signer):
                break
            # Keep each local approval advancement atomic. External artefact
            # storage happens only after all provider participants reconcile.
            with self.env.cr.savepoint():
                recipient.sudo().write(
                    {
                        "status": "completed",
                        "completed_at": fields.Datetime.now(),
                    }
                )
                pending = self.recipient_ids.filtered(
                    lambda item: item.status != "completed"
                ).sorted("sequence")
                self.sudo().write(
                    {
                        "status": "in_progress",
                        "provider_status": "in-progress",
                        "current_recipient_id": pending[:1].id if pending else False,
                        "last_sync_at": fields.Datetime.now(),
                    }
                )
                source = self._source_record()
                if source and hasattr(source, "opensign_event_hook"):
                    source.opensign_event_hook(
                        self.id,
                        "signed",
                        {"signer": {"email": recipient.email}, "reconciled": True},
                    )
        return not self.recipient_ids.filtered(lambda item: item.status != "completed")

    def process_provider_event(self, event_record, payload):
        self.ensure_one()
        raw_event_type = (payload.get("event") or "").strip().lower()
        event_type = {
            "document.created": "created",
            "document.viewed": "viewed",
            "document.signed": "signed",
            "document.approved": "approved",
            "document.declined": "declined",
            "document.revoked": "revoked",
            "document.completed": "completed",
        }.get(raw_event_type, raw_event_type)
        if self.status in TERMINAL_STATUSES and event_type != "completed":
            event_record.sudo().write(
                {"state": "ignored", "safe_message": _("Terminal request.")}
            )
            return True
        provider_payload = payload
        if event_type in ("signed", "approved", "completed") and not (
            payload.get("signer")
            or payload.get("signers")
            or payload.get("recipients")
        ):
            # Some integration webhooks contain only the document ID and
            # event name. Retrieve authoritative signer statuses through the
            # authenticated LHI Sign integration status endpoint.
            provider_payload = self.provider_status_payload()

        recipient = self._recipient_from_payload(payload)
        event_time = event_record.provider_timestamp or fields.Datetime.now()
        if event_type == "viewed" and recipient and recipient.status == "pending":
            recipient.sudo().write({"status": "viewed", "viewed_at": event_time})
        elif event_type in ("signed", "approved"):
            if not recipient:
                # The webhook did not contain signer identity. Reconcile the
                # authoritative provider signer list in strict local sequence.
                completed_before = set(
                    self.recipient_ids.filtered(
                        lambda item: item.status == "completed"
                    ).ids
                )

                self._reconcile_completed_recipients(provider_payload)

                completed_after = set(
                    self.recipient_ids.filtered(
                        lambda item: item.status == "completed"
                    ).ids
                )

                if completed_after == completed_before:
                    raise UserError(
                        _(
                            "The provider signed event did not identify "
                            "a newly completed participant."
                        )
                    )

                self.sudo().write(
                    {
                        "preparation_completed": True,
                        "last_sync_at": fields.Datetime.now(),
                    }
                )

                # Recipient reconciliation already advanced the local route
                # and invoked the source signed-event hook.
                return True

            current_recipient = self.current_recipient_id

            if not current_recipient:
                current_recipient = self.recipient_ids.filtered(
                    lambda item: item.status != "completed"
                ).sorted("sequence")[:1]

                if current_recipient:
                    self.sudo().write(
                        {
                            "status": "in_progress",
                            "provider_status": "in-progress",
                            "preparation_completed": True,
                            "current_recipient_id": current_recipient.id,
                            "last_sync_at": fields.Datetime.now(),
                        }
                    )

            if recipient != current_recipient:
                raise UserError(_("An out-of-order provider action was rejected."))

            recipient.sudo().write(
                {
                    "status": "completed",
                    "completed_at": event_time,
                }
            )

            pending = self.recipient_ids.filtered(
                lambda item: item.status != "completed"
            ).sorted("sequence")

            self.sudo().write(
                {
                    "status": "in_progress",
                    "provider_status": "in-progress",
                    "preparation_completed": True,
                    "current_recipient_id": pending[:1].id if pending else False,
                    "last_sync_at": fields.Datetime.now(),
                }
            )
        elif event_type in ("declined", "revoked"):
            if event_type == "declined" and (
                not recipient or recipient != self.current_recipient_id
            ):
                raise UserError(_("An out-of-order provider decline was rejected."))
            if recipient:
                recipient.sudo().write(
                    {
                        "status": "declined",
                        "decline_reason": payload.get("declineReason")
                        or payload.get("reason")
                        or _("Declined in LHI Sign"),
                    }
                )
            self.sudo().write(
                {
                    "status": "declined" if event_type == "declined" else "cancelled",
                    "provider_status": event_type,
                    "last_sync_at": fields.Datetime.now(),
                }
            )
        elif event_type == "completed":
            if self.status == "completed":
                source = self._source_record()
                if source and hasattr(source, "opensign_completed_hook"):
                    source.opensign_completed_hook(self.id)
                return True
            if not self._reconcile_completed_recipients(provider_payload):
                raise UserError(
                    _(
                        "Provider completion cannot be applied until every "
                        "sequential participant is explicitly confirmed."
                    )
                )
            signed_url = payload.get("file") or f"/signature-requests/{self.provider_request_id}/signed-document"
            certificate_url = payload.get("certificate") or f"/signature-requests/{self.provider_request_id}/certificate"
            if not signed_url or not certificate_url:
                raise UserError(_("The completion event omitted signed artefact URLs."))
            signed_pdf = self.configuration_id.api_download(signed_url)
            certificate = self.configuration_id.api_download(certificate_url)
            if not signed_pdf.startswith(b"%PDF") or not certificate.startswith(
                b"%PDF"
            ):
                raise UserError(
                    _("LHI Sign returned an invalid signed PDF or audit certificate.")
                )
            self.process_callback(
                "completed",
                signed_pdf=signed_pdf,
                signed_hash=hashlib.sha256(signed_pdf).hexdigest(),
                cert=certificate,
            )
        elif event_type not in ("created",):
            raise UserError(_("The provider event type is not supported."))

        source = self._source_record()
        if source and hasattr(source, "opensign_event_hook"):
            source.opensign_event_hook(
                self.id,
                "signed" if event_type == "approved" else event_type,
                payload,
            )
        return True

    def process_callback(
        self,
        status,
        signed_pdf=False,
        signed_hash=False,
        cert=False,
        error=False,
    ):
        """Backward-compatible completion API used by legacy integrations."""
        self.ensure_one()
        vals = {"status": status}
        if status == "completed":
            vals["provider_status"] = "completed"
        log_msg = f"Callback received: Status = {status}\n"
        if signed_pdf:
            signed_content = self.env["lhi.document.item"]._decode_binary_value(
                signed_pdf
            )
            self._store_sharepoint_binary(
                "signed_pdf",
                signed_content,
                "signed_document_item_id",
                "signed",
            )
            vals["signed_pdf_hash"] = (
                signed_hash or hashlib.sha256(signed_content).hexdigest()
            )
        elif signed_hash:
            vals["signed_pdf_hash"] = signed_hash
        if cert:
            certificate_content = self.env["lhi.document.item"]._decode_binary_value(
                cert
            )
            self._store_sharepoint_binary(
                "audit_certificate",
                certificate_content,
                "certificate_document_item_id",
                "certificate",
            )
        if error:
            vals["error_message"] = str(error)[:2000]
            log_msg += "Provider reported a safe error.\n"
        vals["callback_logs"] = (self.callback_logs or "") + log_msg
        self.sudo().write(vals)

        if status == "completed" and (
            not self.signed_stored or (cert and not self.certificate_stored)
        ):
            self.sudo().write(
                {
                    "status": "failed",
                    "error_message": _(
                        "Provider completion was received, but SharePoint did not "
                        "confirm all signed artefacts."
                    ),
                }
            )
            raise UserError(
                _("SharePoint did not confirm every completed signature artefact.")
            )
        if status == "completed":
            source = self._source_record()
            try:
                if source and hasattr(source, "opensign_completed_hook"):
                    source.opensign_completed_hook(self.id)
            except Exception as error:
                self.sudo().write(
                    {
                        "status": "failed",
                        "error_message": str(error)[:2000],
                    }
                )
                raise
        return True

    def action_reconcile(self):
        for signature_request in self:
            if not signature_request.provider_request_id:
                continue
            event = self.env["lhi.opensign.webhook.event"]
            try:
                payload = signature_request.provider_status_payload()
                provider_status = (payload.get("status") or "").lower()
                if (
                    provider_status == "completed"
                    and signature_request.status != "completed"
                ):
                    event = (
                        self.env["lhi.opensign.webhook.event"]
                        .sudo()
                        .create_reconciliation_event(signature_request, payload)
                    )
                    signature_request.process_provider_event(
                        event, {**payload, "event": "completed"}
                    )
                    event.sudo().write(
                        {"state": "processed", "processed_at": fields.Datetime.now()}
                    )
            except Exception as error:
                safe_error = str(error)[:2000]
                if event:
                    event.sudo().write({"state": "failed", "safe_message": safe_error})
                signature_request.sudo().write(
                    {
                        "retry_count": signature_request.retry_count + 1,
                        "error_message": safe_error,
                    }
                )
        return True

    @api.model
    def cron_reconcile_requests(self, batch_size=100):
        requests_to_reconcile = self.sudo().search(
            [
                ("provider_request_id", "!=", False),
                ("status", "not in", list(TERMINAL_STATUSES)),
            ],
            order="last_sync_at asc nulls first, id",
            limit=min(max(int(batch_size), 1), 500),
        )
        requests_to_reconcile.action_reconcile()

    @api.model
    def _lhi_create_memo_signature_draft(self, signature_request, redirect_url):
        """Service contract v1 method for creating provider draft and validating preparation URL."""
        req = signature_request.sudo()
        req.action_create_provider_draft(redirect_url=redirect_url)
        if not req.provider_request_id or not req.provider_preparation_url:
            raise UserError(_("LHI Sign did not return a valid provider draft or preparation URL."))
        return {
            "contract_version": self.MEMO_SIGNATURE_CONTRACT_VERSION,
            "signature_request_id": req.id,
            "provider_request_id": req.provider_request_id,
            "preparation_url": req.provider_preparation_url,
            "outcome": "confirmed",
        }
        return True
