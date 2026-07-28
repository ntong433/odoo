import hashlib
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import timedelta
from urllib.parse import quote
from xml.sax.saxutils import escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EDITABLE_STATES = {"draft", "authoring", "returned", "failed"}
TERMINAL_STATES = {"completed", "rejected", "expired", "cancelled", "superseded"}
STATE_TRANSITIONS = {
    "draft": {"authoring", "failed", "cancelled"},
    "authoring": {"ready_for_preparation", "preparing", "failed", "cancelled"},
    "ready_for_preparation": {"preparing", "authoring", "failed", "cancelled"},
    "preparing": {"requester_signature_pending", "failed", "returned", "cancelled"},
    "requester_signature_pending": {
        "submitted",
        "under_approval",
        "failed",
        "returned",
        "rejected",
        "expired",
        "cancelled",
    },
    "submitted": {
        "under_approval",
        "final_signature_pending",
        "returned",
        "rejected",
        "expired",
        "failed",
        "cancelled",
    },
    "under_approval": {
        "final_signature_pending",
        "completed",
        "returned",
        "rejected",
        "expired",
        "failed",
        "cancelled",
    },
    "final_signature_pending": {
        "completed",
        "returned",
        "rejected",
        "expired",
        "failed",
        "cancelled",
    },
    "returned": {"authoring", "preparing", "failed", "cancelled"},
    "failed": {"authoring", "preparing", "returned", "cancelled"},
    "rejected": {"superseded"},
    "completed": {"superseded"},
    "expired": {"superseded"},
    "cancelled": {"superseded"},
    "superseded": set(),
}


class LhiMemo(models.Model):
    _name = "lhi.memo"
    _description = "LHI Memo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    uuid = fields.Char(
        default=lambda self: str(uuid.uuid4()), required=True, copy=False, index=True
    )
    name = fields.Char(
        default="New",
        required=True,
        copy=False,
        readonly=True,
        tracking=True,
        index=True,
    )
    title = fields.Char(required=True, tracking=True)
    memo_category_id = fields.Many2one(
        "lhi.memo.category", required=True, ondelete="restrict", tracking=True
    )
    subject = fields.Char(required=True, tracking=True)
    purpose = fields.Text(required=True, tracking=True)
    priority = fields.Selection(
        [("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")],
        default="normal",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("authoring", "Authoring in Word"),
            ("ready_for_preparation", "Ready for Preparation"),
            ("preparing", "Preparing in LHI Sign"),
            ("requester_signature_pending", "Requester Signature Pending"),
            ("submitted", "Submitted"),
            ("under_approval", "Under Approval"),
            ("final_signature_pending", "Final Signature Pending"),
            ("completed", "Completed"),
            ("returned", "Returned for Correction"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("failed", "Integration Failed"),
            ("superseded", "Superseded"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    requester_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        index=True,
    )
    requester_employee_id = fields.Many2one(
        "hr.employee", compute="_compute_requester_employee", store=True, readonly=True
    )
    department_id = fields.Many2one(
        "lhi.department",
        required=True,
        default=lambda self: self.env.user.lhi_department_ids[:1],
        tracking=True,
        index=True,
    )
    office_id = fields.Many2one(
        "lhi.office",
        default=lambda self: self.env.user.lhi_office_ids[:1],
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    recipient_user_ids = fields.Many2many(
        "res.users", string="Recipients", tracking=True
    )
    recipient_description = fields.Char(tracking=True)
    preparation_officer_ids = fields.Many2many(
        "res.users",
        "lhi_memo_preparation_officer_rel",
        "memo_id",
        "user_id",
        string="Authorized Preparation Officers",
        domain=lambda self: [
            (
                "group_ids",
                "in",
                [
                    self.env.ref(
                        "lhi_signature_bridge.group_lhi_signature_preparation_officer"
                    ).id
                ],
            )
        ],
    )

    work_context = fields.Selection(
        [
            ("standalone_departmental", "Standalone Departmental"),
            ("procurement_related", "Procurement Related"),
            ("project_linked", "Project Linked"),
            ("grant_linked", "Grant Linked"),
            ("operations_related", "Operations Related"),
            ("it_related", "IT Related"),
            ("hr_related", "HR Related"),
            ("other", "Other"),
        ],
        default="standalone_departmental",
        required=True,
        tracking=True,
    )
    project_id = fields.Many2one("lhi.project", tracking=True)
    grant_id = fields.Many2one("lhi.award", string="Grant/Award", tracking=True)
    procurement_reference_id = fields.Many2one("lhi.purchase.request", tracking=True)
    related_model = fields.Char(
        compute="_compute_related_resource", store=True, readonly=True
    )
    related_record_id = fields.Integer(
        compute="_compute_related_resource", store=True, readonly=True
    )
    amount = fields.Monetary(currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )

    draft_date = fields.Date(
        default=fields.Date.context_today, required=True, readonly=True
    )
    required_date = fields.Date(tracking=True)
    submitted_at = fields.Datetime(readonly=True)
    requester_signed_at = fields.Datetime(readonly=True)
    approved_at = fields.Datetime(readonly=True)
    final_signed_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    expiry_date = fields.Datetime(readonly=True)

    source_docx_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    source_docx_web_url = fields.Char(readonly=True, copy=False)
    source_docx_version_id = fields.Char(
        readonly=True,
        copy=False,
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    source_docx_etag = fields.Char(
        readonly=True,
        copy=False,
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    document_template_id = fields.Many2one(
        "lhi.memo.document.template",
        string="Assigned Template",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    template_version_snapshot = fields.Char(
        string="Template Version Snapshot", readonly=True, copy=False
    )
    template_sharepoint_version_snapshot = fields.Char(
        string="SharePoint Template Version Snapshot", readonly=True, copy=False
    )
    template_sharepoint_drive_id_snapshot = fields.Char(
        string="Template Drive ID Snapshot", readonly=True, copy=False
    )
    template_sharepoint_item_id_snapshot = fields.Char(
        string="Template Item ID Snapshot", readonly=True, copy=False
    )
    template_sharepoint_etag_snapshot = fields.Char(
        string="Template ETag Snapshot", readonly=True, copy=False
    )
    document_created_at = fields.Datetime(
        string="Document Created At", readonly=True, copy=False
    )
    document_created_by = fields.Many2one(
        "res.users", string="Document Created By", readonly=True, copy=False
    )
    document_state = fields.Selection(
        [
            ("not_created", "Not Created"),
            ("creating", "Creating"),
            ("created", "Created"),
            ("failed", "Failed"),
        ],
        string="Document Status",
        default="not_created",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )

    source_pdf_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    source_pdf_hash = fields.Char(
        readonly=True,
        copy=False,
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    signed_pdf_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    signed_pdf_hash = fields.Char(
        readonly=True,
        copy=False,
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    certificate_item_id = fields.Many2one(
        "lhi.document.item", readonly=True, copy=False, ondelete="restrict"
    )
    has_word_document = fields.Boolean(compute="_compute_document_flags")
    has_submitted_pdf = fields.Boolean(compute="_compute_document_flags")
    has_signed_pdf = fields.Boolean(compute="_compute_document_flags")
    has_certificate = fields.Boolean(compute="_compute_document_flags")

    signature_request_id = fields.Many2one(
        "lhi.opensign.request", readonly=True, copy=False, ondelete="restrict"
    )
    signature_request_ids = fields.One2many(
        "lhi.opensign.request",
        "memo_id",
        string="Signature Request History",
        readonly=True,
    )
    provider_request_id = fields.Char(
        related="signature_request_id.provider_request_id",
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    provider_preparation_url = fields.Char(
        related="signature_request_id.provider_preparation_url",
        groups="lhi_signature_bridge.group_lhi_signature_admin",
    )
    provider_status = fields.Char(related="signature_request_id.provider_status")
    preparation_completed = fields.Boolean(
        related="signature_request_id.preparation_completed"
    )
    requester_signature_completed = fields.Boolean(readonly=True)
    final_signature_completed = fields.Boolean(readonly=True)
    current_recipient_id = fields.Many2one(
        related="signature_request_id.current_recipient_id", readonly=True
    )
    current_recipient_user_id = fields.Many2one(
        related="signature_request_id.current_recipient_id.user_id", readonly=True
    )
    last_sync_at = fields.Datetime(
        related="signature_request_id.last_sync_at", readonly=True
    )
    integration_error_code = fields.Char(
        readonly=True, groups="lhi_signature_bridge.group_lhi_signature_admin"
    )
    integration_error_message = fields.Text(
        readonly=True, groups="lhi_signature_bridge.group_lhi_signature_admin"
    )

    approval_request_id = fields.Many2one(
        "lhi.approval.request", readonly=True, copy=False, ondelete="restrict"
    )
    approver_line_ids = fields.One2many(
        "lhi.memo.approver.line", "memo_id", string="Approval Timeline", readonly=True
    )
    current_approval_sequence = fields.Integer(readonly=True)
    return_reason = fields.Text(tracking=True)
    rejection_reason = fields.Text(tracking=True)
    supersedes_memo_id = fields.Many2one("lhi.memo", readonly=True, ondelete="restrict")
    superseded_by_memo_id = fields.Many2one(
        "lhi.memo", readonly=True, ondelete="restrict"
    )

    _uuid_unique = models.Constraint("unique(uuid)", "Memo UUIDs must be unique.")
    _name_company_unique = models.Constraint(
        "unique(name, company_id)", "The memo reference must be unique per company."
    )

    @api.depends("requester_id", "requester_id.employee_id")
    def _compute_requester_employee(self):
        for memo in self:
            memo.requester_employee_id = memo.requester_id.employee_id[:1]

    @api.depends("project_id", "grant_id", "procurement_reference_id", "work_context")
    def _compute_related_resource(self):
        for memo in self:
            record = False
            if memo.work_context == "procurement_related":
                record = memo.procurement_reference_id
            elif memo.work_context == "project_linked":
                record = memo.project_id
            elif memo.work_context == "grant_linked":
                record = memo.grant_id
            memo.related_model = record._name if record else False
            memo.related_record_id = record.id if record else 0

    @api.depends(
        "source_docx_item_id.storage_state",
        "source_pdf_item_id.storage_state",
        "signed_pdf_item_id.storage_state",
        "certificate_item_id.storage_state",
    )
    def _compute_document_flags(self):
        for memo in self:
            memo.has_word_document = bool(
                memo.source_docx_item_id
                and memo.source_docx_item_id.storage_state == "available"
            )
            memo.has_submitted_pdf = bool(
                memo.source_pdf_item_id
                and memo.source_pdf_item_id.storage_state == "available"
            )
            memo.has_signed_pdf = bool(
                memo.signed_pdf_item_id
                and memo.signed_pdf_item_id.storage_state == "available"
            )
            memo.has_certificate = bool(
                memo.certificate_item_id
                and memo.certificate_item_id.storage_state == "available"
            )

    @api.constrains(
        "work_context", "project_id", "grant_id", "procurement_reference_id"
    )
    def _check_context_reference(self):
        for memo in self:
            required = {
                "project_linked": memo.project_id,
                "grant_linked": memo.grant_id,
                "procurement_related": memo.procurement_reference_id,
            }.get(memo.work_context)
            if (
                memo.work_context
                in (
                    "project_linked",
                    "grant_linked",
                    "procurement_related",
                )
                and not required
            ):
                raise ValidationError(
                    _("Select the reference required by this work context.")
                )

    @api.constrains("preparation_officer_ids")
    def _check_preparation_officers(self):
        group = self.env.ref(
            "lhi_signature_bridge.group_lhi_signature_preparation_officer"
        )
        for memo in self:
            invalid = memo.preparation_officer_ids.filtered(
                lambda user: group not in user.all_group_ids
            )
            if invalid:
                raise ValidationError(
                    _("Only protected signature preparation officers may be assigned.")
                )

    @api.constrains(
        "company_id",
        "requester_id",
        "department_id",
        "office_id",
        "memo_category_id",
        "project_id",
        "grant_id",
        "procurement_reference_id",
        "recipient_user_ids",
        "preparation_officer_ids",
    )
    def _check_company_scope(self):
        for memo in self:
            if memo.company_id not in memo.requester_id.company_ids:
                raise ValidationError(
                    _("The requester is not authorized for the memo company.")
                )
            for record in (
                memo.department_id,
                memo.office_id,
                memo.memo_category_id,
                memo.project_id,
                memo.grant_id,
                memo.procurement_reference_id,
            ):
                if (
                    record
                    and "company_id" in record._fields
                    and record.company_id
                    and record.company_id != memo.company_id
                ):
                    raise ValidationError(
                        _("Memo business references must belong to the memo company.")
                    )
            users = memo.recipient_user_ids | memo.preparation_officer_ids
            if users.filtered(lambda user: memo.company_id not in user.company_ids):
                raise ValidationError(
                    _("Every memo participant must be authorized for the memo company.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("lhi.memo") or "New"
            requester = (
                self.env["res.users"].browse(vals.get("requester_id")) or self.env.user
            )
            if not vals.get("department_id") and requester.lhi_department_ids:
                vals["department_id"] = requester.lhi_department_ids[0].id
            if not vals.get("company_id"):
                vals["company_id"] = requester.company_id.id
            category = self.env["lhi.memo.category"].browse(
                vals.get("memo_category_id")
            )
            company_id = vals.get("company_id") or requester.company_id.id or self.env.company.id
            template = self.env["lhi.memo.document.template"].search(
                [
                    ("is_default", "=", True),
                    ("active", "=", True),
                    ("company_id", "=", company_id),
                ],
                limit=1,
            )
            if template:
                vals.setdefault("document_template_id", template.id)
                vals.setdefault("template_version_snapshot", template.version)
                vals.setdefault("template_sharepoint_version_snapshot", template.sharepoint_version)
                vals.setdefault("template_sharepoint_drive_id_snapshot", template.sharepoint_drive_id)
                vals.setdefault("template_sharepoint_item_id_snapshot", template.sharepoint_item_id)
                vals.setdefault("template_sharepoint_etag_snapshot", template.sharepoint_etag)

            vals.setdefault("document_state", "not_created")
        records = super().create(vals_list)
        return records

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        technical = {
            "state",
            "source_docx_item_id",
            "source_docx_web_url",
            "source_docx_version_id",
            "source_docx_etag",
            "source_pdf_item_id",
            "source_pdf_hash",
            "signed_pdf_item_id",
            "signed_pdf_hash",
            "certificate_item_id",
            "signature_request_id",
            "approval_request_id",
            "provider_request_id",
            "provider_preparation_url",
            "provider_status",
            "preparation_completed",
            "requester_signature_completed",
            "final_signature_completed",
            "current_approval_sequence",
            "integration_error_code",
            "integration_error_message",
            "submitted_at",
            "requester_signed_at",
            "approved_at",
            "final_signed_at",
            "completed_at",
        }
        if technical.intersection(vals):
            raise AccessError(
                _("Technical memo fields can only be changed by workflow services.")
            )
        for memo in self:
            is_memo_admin = self.env.user.has_group(
                "lhi_memo_management.group_lhi_memo_admin"
            )
            reason_only = set(vals) <= {"return_reason", "rejection_reason"}
            if reason_only and memo._is_current_approver(self.env.user):
                continue
            if not is_memo_admin and (
                memo.requester_id != self.env.user or memo.state not in EDITABLE_STATES
            ):
                raise AccessError(_("Only the requester may edit an editable memo."))
        return super().write(vals)

    def unlink(self):
        for memo in self:
            if memo.state != "draft":
                raise UserError(_("Only an unstarted draft memo may be deleted."))
        return super().unlink()

    @api.onchange("memo_category_id")
    def _onchange_memo_category_id(self):
        if self.memo_category_id:
            self.recipient_user_ids = self.memo_category_id.default_recipient_ids

    @staticmethod
    def _safe_filename(reference):
        return re.sub(r"[^A-Za-z0-9._-]+", "-", reference or "Memo").strip("-")

    def _docx_metadata(self):
        self.ensure_one()
        return {
            "MEMO_REFERENCE": self.name,
            "MEMO_TITLE": self.title,
            "MEMO_DATE": fields.Date.to_string(self.draft_date),
            "MEMO_REQUESTER": self.requester_id.name,
            "MEMO_DEPARTMENT": self.department_id.name,
            "MEMO_RECIPIENT": ", ".join(self.recipient_user_ids.mapped("name"))
            or self.recipient_description
            or "",
            "MEMO_SUBJECT": self.subject,
            "MEMO_PURPOSE": self.purpose,
        }

    def _generated_docx(self):
        self.ensure_one()
        data = self._docx_metadata()
        paragraphs = [
            ("LIFE HELPERS INITIATIVE", True),
            ("INTERNAL MEMORANDUM", True),
            (f"Reference: {data['MEMO_REFERENCE']}", False),
            (f"Date: {data['MEMO_DATE']}", False),
            (f"From: {data['MEMO_REQUESTER']} ({data['MEMO_DEPARTMENT']})", False),
            (f"To: {data['MEMO_RECIPIENT']}", False),
            (f"Subject: {data['MEMO_SUBJECT']}", True),
            (data["MEMO_PURPOSE"], False),
            ("Continue authoring this memo in Microsoft Word for the web.", False),
        ]
        body = []
        for text, bold in paragraphs:
            run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
            body.append(
                f'<w:p><w:r>{run_props}<w:t xml:space="preserve">{escape(text or "")}</w:t></w:r></w:p>'
            )
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{"".join(body)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )
        relationships = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        )
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", relationships)
            archive.writestr("word/document.xml", document)
        return output.getvalue()

    def _starter_docx(self):
        self.ensure_one()
        starter = self.memo_category_id.starter_document_item_id
        if not starter:
            return self._generated_docx()
        content = starter.download_bytes(auth_context="application")
        source = io.BytesIO(content)
        output = io.BytesIO()
        replacements = {
            f"{{{{{key}}}}}": escape(value or "")
            for key, value in self._docx_metadata().items()
        }
        with (
            zipfile.ZipFile(source, "r") as original,
            zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as result,
        ):
            if "word/document.xml" not in original.namelist():
                raise UserError(_("The configured Word starter document is invalid."))
            for info in original.infolist():
                payload = original.read(info.filename)
                if info.filename == "word/document.xml":
                    text = payload.decode("utf-8")
                    for marker, value in replacements.items():
                        text = text.replace(marker, value)
                    payload = text.encode("utf-8")
                result.writestr(info, payload)
        return output.getvalue()

    def _safe_memo_filename(self):
        self.ensure_one()
        ref_part = (self.name or "MEMO").replace("/", "-").replace("\\", "-")
        subject_part = (self.subject or "").strip()
        invalid_chars = r'["*:<>?/\\|]'
        sanitized_subject = re.sub(invalid_chars, "", subject_part).strip()
        if sanitized_subject:
            if len(sanitized_subject) > 60:
                sanitized_subject = sanitized_subject[:60].strip()
            return f"{ref_part} - {sanitized_subject}.docx"
        return f"{ref_part}.docx"

    def _validate_before_opening_word(self):
        self.ensure_one()
        missing_fields = []
        if not self.name or self.name == "New":
            missing_fields.append("Memo Reference")
        if not self.requester_id:
            missing_fields.append("Requester (FROM)")
        if not self.recipient_user_ids and not self.recipient_description:
            missing_fields.append("Recipients (TO)")
        if not self.draft_date and not self.create_date:
            missing_fields.append("Memo Date")
        if not self.subject:
            missing_fields.append("Subject")

        if not self.document_template_id:
            template = self.env["lhi.memo.document.template"].search(
                [
                    ("is_default", "=", True),
                    ("active", "=", True),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if template:
                self.sudo().write({
                    "document_template_id": template.id,
                    "template_version_snapshot": template.version,
                    "template_sharepoint_version_snapshot": template.sharepoint_version,
                    "template_sharepoint_drive_id_snapshot": template.sharepoint_drive_id,
                    "template_sharepoint_item_id_snapshot": template.sharepoint_item_id,
                    "template_sharepoint_etag_snapshot": template.sharepoint_etag,
                })
            else:
                missing_fields.append("Active Default Memo Template Configuration")

        if self.document_template_id and not self.template_sharepoint_drive_id_snapshot:
            missing_fields.append("SharePoint Drive ID in Active Template")
        if self.document_template_id and not self.template_sharepoint_item_id_snapshot:
            missing_fields.append("SharePoint Template File Item ID in Active Template")

        if self.state in ("cancelled", "superseded"):
            raise UserError(_("Cannot create or open a Word document for a cancelled or superseded memo."))

        if missing_fields:
            bullet_list = "\n".join(f"• {field}" for field in missing_fields)
            raise UserError(
                _("The memo document cannot be created because the following required details are missing:\n\n%s\n\nPlease complete these details before proceeding.")
                % bullet_list
            )

    def _download_master_template_bytes(self):
        self.ensure_one()
        drive_id = self.template_sharepoint_drive_id_snapshot or (
            self.document_template_id and self.document_template_id.sharepoint_drive_id
        )
        item_id = self.template_sharepoint_item_id_snapshot or (
            self.document_template_id and self.document_template_id.sharepoint_item_id
        )

        if not drive_id or not item_id:
            raise UserError(_("No active default memo template has been configured."))

        connection = self.env["lhi.graph.connection"]._get_active_connection(self.company_id)
        if not connection:
            raise UserError(_("The official memo template could not be retrieved from SharePoint because no active Microsoft Graph connection exists."))

        try:
            response = connection.lhi_binary_request(
                "GET",
                f"/drives/{quote(drive_id)}/items/{quote(item_id)}/content",
                auth_context="application",
                expected_statuses={200},
                allow_redirects=True,
            )
        except Exception as error:
            raise UserError(_("The official memo template could not be retrieved from SharePoint. Please contact the Memo Administrator."))

        if not response or not response.content:
            raise UserError(
                _("The official memo template downloaded from SharePoint is empty.")
            )

        return response.content

    def _build_template_rendering_context(self):
        self.ensure_one()
        memo_date_val = self.draft_date or self.create_date or fields.Datetime.now()
        formatted_date = memo_date_val.strftime("%d %B %Y")

        from_name = self.requester_id.name or ""
        from_title = getattr(self.requester_id, "job_title", False) or (
            self.requester_employee_id.job_title if hasattr(self, "requester_employee_id") and self.requester_employee_id else ""
        )
        from_display = f"{from_name} ({from_title})" if from_title else from_name

        if self.recipient_description:
            to_display = self.recipient_description
        elif self.recipient_user_ids:
            to_display = ", ".join(self.recipient_user_ids.mapped("name"))
        else:
            to_display = ""

        project_name = self.project_id.name if hasattr(self, "project_id") and self.project_id else ""
        project_code = getattr(self.project_id, "code", "") if hasattr(self, "project_id") and self.project_id else ""
        priority_label = dict(self._fields["priority"].selection).get(self.priority, "") if hasattr(self, "priority") and self.priority else ""

        return {
            "memo_reference": self.name or "",
            "from_display": from_display,
            "from_name": from_name,
            "from_designation": from_title or "",
            "to_display": to_display,
            "memo_date": formatted_date,
            "subject": self.subject or "",
            "memo_body": self.purpose or "",
            "priority": priority_label,
            "project_name": project_name,
            "project_code": project_code,
            "revision_number": str(getattr(self, "revision_number", 1) or 1),
        }

    def _create_word_document_from_template(self):
        self.ensure_one()
        # Acquire row lock
        self.env.cr.execute("SELECT id FROM lhi_memo WHERE id = %s FOR UPDATE NOWAIT", [self.id])

        if self.source_docx_item_id and self.source_docx_item_id.storage_state == "available":
            return self.source_docx_item_id

        self.sudo().write({"document_state": "creating"})

        try:
            template_bytes = self._download_master_template_bytes()

            from ..services.word_template_service import WordTemplateService

            WordTemplateService.validate_template(template_bytes)

            context = self._build_template_rendering_context()
            rendered_bytes = WordTemplateService.render_template(template_bytes, context)

            filename = self._safe_memo_filename()
            item = self.env["lhi.document.item"].create_from_bytes(
                name=filename,
                content=rendered_bytes,
                mime_type=DOCX_MIME,
                linked_model=self._name,
                linked_record_id=self.id,
                linked_field="source_docx_item_id",
                requested_by=self.requester_id or self.env.user,
                synchronous=True,
            )

            if item.storage_state != "available" or not item.sharepoint_item_id:
                raise UserError(_("SharePoint did not confirm the generated memo Word document."))

            self.sudo().write({
                "source_docx_item_id": item.id,
                "source_docx_web_url": item.sharepoint_web_url,
                "document_created_at": fields.Datetime.now(),
                "document_created_by": self.env.user.id,
                "document_state": "created",
                "integration_error_code": False,
                "integration_error_message": False,
            })

            if self.state not in ("authoring", "ready_for_preparation", "preparing", "submitted", "under_approval", "completed"):
                self._transition("authoring")

            self.message_post(
                body=_("Word document created successfully from template '%s' (v%s) and saved to SharePoint.")
                % (self.document_template_id.name if self.document_template_id else "Default", self.template_version_snapshot or "1.0")
            )
            return item
        except Exception as error:
            self.sudo().write({"document_state": "failed"})
            _logger.error("Failed to create Word document from template for memo %s: %s", self.name, error)
            raise

    def _create_word_document(self, *, retry_failed=False):
        return self._create_word_document_from_template()
        if self.state != "authoring":
            self._transition("authoring")
        self.message_post(
            body=_("The SharePoint Word document is ready for authoring.")
        )
        self._notify_users(
            self.requester_id,
            _("Memo Word document ready"),
            _("Your memo is ready to edit in Microsoft Word for the web."),
        )
        return item

    def _transition(self, target_state, extra_vals=None):
        self.ensure_one()
        if target_state == self.state:
            return True
        source_state = self.state
        if target_state not in STATE_TRANSITIONS.get(self.state, set()):
            raise UserError(
                _("The memo cannot move from %(source)s to %(target)s.")
                % {"source": self.state, "target": target_state}
            )
        vals = {"state": target_state, **(extra_vals or {})}
        self.sudo().write(vals)
        self.env["lhi.audit.log"].with_company(self.company_id).create_event(
            event_type="approval_action",
            res_model=self._name,
            res_id=self.id,
            description=_("Memo state changed from %s to %s.")
            % (source_state, target_state),
        )
        return True

    def _record_integration_failure(self, code, error):
        self.ensure_one()
        safe_message = str(error)[:2000]
        vals = {
            "integration_error_code": code,
            "integration_error_message": safe_message,
        }
        if self.state not in TERMINAL_STATES:
            vals["state"] = "failed"
        self.sudo().write(vals)
        self.message_post(
            body=_(
                "The memo integration could not complete safely. No document or "
                "signature status was assumed. A retry or administrator review is required."
            )
        )
        self._notify_users(
            self.requester_id,
            _("Memo integration needs attention"),
            _("A memo operation failed safely. Retry it or contact support."),
            schedule_activity=True,
        )
        _logger.warning("Memo %s integration failure %s", self.name, code)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Memo integration needs attention"),
                "message": _(
                    "The operation failed safely. Please retry or contact support."
                ),
                "type": "warning",
                "sticky": True,
            },
        }

    def _notify_users(self, users, summary, body, *, schedule_activity=False):
        """Send bounded workflow notifications without duplicating activities."""
        self.ensure_one()
        users = users.filtered(lambda user: user.active and not user.share)
        if not users:
            return True
        self.sudo().message_post(
            body=body,
            partner_ids=users.partner_id.ids,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        if schedule_activity:
            activity_type = self.env.ref("mail.mail_activity_data_todo")
            model_id = self.env["ir.model"]._get_id(self._name)
            for user in users:
                existing = (
                    self.env["mail.activity"]
                    .sudo()
                    .search(
                        [
                            ("activity_type_id", "=", activity_type.id),
                            ("res_model_id", "=", model_id),
                            ("res_id", "=", self.id),
                            ("user_id", "=", user.id),
                            ("summary", "=", summary),
                        ],
                        limit=1,
                    )
                )
                if not existing:
                    self.sudo().activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=user.id,
                        summary=summary,
                        note=body,
                    )
        return True

    def _ensure_requester_or_preparer(self):
        self.ensure_one()
        allowed = (
            self.requester_id == self.env.user
            or self.env.user in self.preparation_officer_ids
            or self.env.user.has_group("lhi_signature_bridge.group_lhi_signature_admin")
        )
        if not allowed:
            raise AccessError(
                _(
                    "Only the requester or an authorized preparation officer may prepare this memo."
                )
            )
        if (
            not self.requester_id.entra_object_id
            or not self.requester_id.entra_tenant_id
        ):
            raise UserError(
                _(
                    "The requester must have a synchronized immutable Microsoft Entra identity."
                )
            )

    @staticmethod
    def _bounded_response_content(response, maximum_bytes):
        headers = getattr(response, "headers", {}) or {}
        declared_size = headers.get("Content-Length")
        if (
            declared_size
            and declared_size.isdigit()
            and int(declared_size) > maximum_bytes
        ):
            raise UserError(
                _("The Microsoft 365 document exceeds the configured limit.")
            )
        iterator = getattr(response, "iter_content", None)
        if not callable(iterator):
            content = response.content
            if len(content) > maximum_bytes:
                raise UserError(
                    _("The Microsoft 365 document exceeds the configured limit.")
                )
            return content
        chunks = []
        size = 0
        for chunk in iterator(chunk_size=1024 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > maximum_bytes:
                raise UserError(
                    _("The Microsoft 365 document exceeds the configured limit.")
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _capture_current_pdf(self, *, retry_failed=False):
        self.ensure_one()
        item = self.source_docx_item_id
        if not item or item.storage_state != "available":
            raise UserError(_("The Word document is not confirmed in SharePoint."))
        connection = item.graph_connection_id
        resource = f"/drives/{quote(item.sharepoint_drive_id)}/items/{quote(item.sharepoint_item_id)}"
        metadata = connection.graph_request(
            "GET",
            resource,
            auth_context="application",
            params={
                "$select": "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,lastModifiedBy,parentReference,file"
            },
        )
        if metadata.get("id") != item.sharepoint_item_id:
            raise UserError(_("SharePoint returned a different Word DriveItem."))
        policy = self.env["lhi.document.storage.policy"].resolve_policy(
            self._name, "source_docx_item_id", self.company_id
        )
        if not policy:
            raise UserError(_("No SharePoint storage policy is configured for memos."))
        maximum_bytes = policy.maximum_size_mb * 1024 * 1024
        docx_response = connection.lhi_binary_request(
            "GET",
            f"{resource}/content",
            auth_context="application",
            expected_statuses={200},
            stream=True,
        )
        docx_content = self._bounded_response_content(docx_response, maximum_bytes)
        if not docx_content:
            raise UserError(_("SharePoint returned an empty Word document."))
        pdf_response = connection.lhi_binary_request(
            "GET",
            f"{resource}/content?format=pdf",
            auth_context="application",
            expected_statuses={200},
            stream=True,
        )
        pdf_content = self._bounded_response_content(pdf_response, maximum_bytes)
        metadata_after = connection.graph_request(
            "GET",
            resource,
            auth_context="application",
            params={
                "$select": "id,size,eTag,cTag,webUrl,lastModifiedDateTime,lastModifiedBy,parentReference,file"
            },
        )
        version = metadata.get("cTag") or metadata.get("eTag")
        version_after = metadata_after.get("cTag") or metadata_after.get("eTag")
        if version != version_after or metadata.get("eTag") != metadata_after.get(
            "eTag"
        ):
            raise UserError(
                _("The Word document changed during PDF capture. Save it and retry.")
            )
        if not pdf_content.startswith(b"%PDF"):
            raise UserError(_("Microsoft 365 did not return a valid PDF conversion."))
        item.sudo().write(
            {
                "file_size": len(docx_content),
                "checksum": hashlib.sha256(docx_content).hexdigest(),
                "sha1_checksum": hashlib.sha1(docx_content).hexdigest(),
            }
        )
        # The caller has already passed memo record rules. Updating only the
        # integration-owned DriveItem metadata is a deliberately narrow service
        # elevation; it does not bypass access to the linked memo.
        item.sudo()._apply_drive_item(metadata_after)
        pdf_hash = hashlib.sha256(pdf_content).hexdigest()
        if self.state == "returned" and self.signature_request_ids.filtered(
            lambda request: request.source_pdf_hash == pdf_hash
        ):
            raise UserError(
                _(
                    "The returned memo has not changed. Save a corrected Word version first."
                )
            )
        pdf_item = self.env["lhi.document.item"].create_from_bytes(
            name=f"{self._safe_filename(self.name)}-Submitted.pdf",
            content=pdf_content,
            mime_type="application/pdf",
            linked_model=self._name,
            linked_record_id=self.id,
            linked_field="source_pdf_item_id",
            requested_by=self.requester_id,
            synchronous=True,
        )
        if retry_failed and pdf_item.storage_state != "available":
            try:
                pdf_item.sudo().write(
                    {
                        "storage_state": "pending",
                        "upload_state": "pending",
                        "last_error": False,
                    }
                )
                pdf_item.sudo().action_upload()
            except Exception as error:
                pdf_item.sudo()._mark_failed(error, enqueue=True)
                raise
        if pdf_item.storage_state != "available":
            raise UserError(_("SharePoint did not confirm the submitted memo PDF."))
        self.sudo().write(
            {
                "source_docx_version_id": version,
                "source_docx_etag": metadata.get("eTag"),
                "source_docx_web_url": metadata_after.get("webUrl")
                or item.sharepoint_web_url,
                "source_pdf_item_id": pdf_item.id,
                "source_pdf_hash": pdf_hash,
            }
        )
        return pdf_item, pdf_hash

    def _lhi_approval_matrix_for_request(self, approval_request):
        self.ensure_one()
        matrix = self.memo_category_id.approval_matrix_id
        if matrix and (
            matrix.document_type != "memo"
            or matrix.company_id != self.company_id
            or not matrix.active
        ):
            raise UserError(_("The memo category approval route is not valid."))
        if matrix and (
            matrix.currency_id != approval_request.currency_id
            or approval_request.amount < matrix.min_amount
            or (matrix.max_amount > 0 and approval_request.amount > matrix.max_amount)
            or (
                matrix.department_ids
                and self.department_id not in matrix.department_ids
            )
            or (matrix.office_ids and self.office_id not in matrix.office_ids)
            or (matrix.award_ids and self.grant_id not in matrix.award_ids)
            or (matrix.project_ids and self.project_id not in matrix.project_ids)
        ):
            raise UserError(
                _(
                    "The memo category approval route does not match the amount "
                    "or organizational context."
                )
            )
        return matrix

    def _prepare_approval_route(self):
        self.ensure_one()
        active_lines = self._active_approver_lines()
        if (
            self.approval_request_id
            and self.approval_request_id.state == "draft"
            and self.approval_request_id.line_ids
            and active_lines
        ):
            return self.approval_request_id, active_lines
        request_values = {
            "res_model": self._name,
            "res_id": self.id,
            "document_type": "memo",
            "amount": self.amount,
            "currency_id": self.currency_id.id,
            "creator_id": self.requester_id.id,
            "company_id": self.company_id.id,
            "department_id": self.department_id.id,
            "office_id": self.office_id.id,
            "award_id": self.grant_id.id,
            "project_id": self.project_id.id,
        }
        approval_request = (
            self.env["lhi.approval.request"]
            .with_company(self.company_id)
            .with_user(self.requester_id)
            .create(request_values)
        )
        approval_request.action_prepare()
        if not approval_request.line_ids:
            raise UserError(_("The memo approval route has no participants."))
        values = []
        cycle_number = max(self.approver_line_ids.mapped("cycle_number") or [0]) + 1
        participant_sequence = 10
        final_request_line = approval_request.line_ids.sorted("sequence")[-1]
        for request_line in approval_request.line_ids.sorted("sequence"):
            users = request_line.approver_ids.sorted("id")
            if request_line.approval_type == "any" and len(users) != 1:
                raise UserError(
                    _("Memo stage '%s' must resolve to exactly one approver.")
                    % request_line.name
                )
            if (
                request_line == final_request_line
                and self.memo_category_id.final_signature_required
                and len(users) != 1
            ):
                raise UserError(
                    _("The final memo signature stage must resolve to one authority.")
                )
            for user in users:
                values.append(
                    {
                        "memo_id": self.id,
                        "cycle_number": cycle_number,
                        "sequence": participant_sequence,
                        "stage_name": request_line.name,
                        "approver_user_id": user.id,
                        "approval_request_line_id": request_line.id,
                        "participant_role": (
                            "final_signer"
                            if request_line == final_request_line
                            and self.memo_category_id.final_signature_required
                            else "approver"
                        ),
                    }
                )
                participant_sequence += 10
        lines = self.env["lhi.memo.approver.line"].sudo().create(values)
        self.sudo().write(
            {
                "approval_request_id": approval_request.id,
                "current_approval_sequence": lines[:1].sequence if lines else 0,
            }
        )
        return approval_request, lines

    def _active_approver_lines(self):
        self.ensure_one()
        if not self.approval_request_id:
            return self.env["lhi.memo.approver.line"]
        return self.approver_line_ids.filtered(
            lambda line: (
                line.approval_request_line_id.request_id == self.approval_request_id
            )
        )

    def _recipient_identity(self, user):
        self.ensure_one()
        if self.company_id not in user.company_ids:
            raise UserError(
                _("Every memo participant must be authorized for the memo company.")
            )
        if not user.entra_object_id or not user.entra_tenant_id:
            raise UserError(
                _(
                    "Every memo participant must have a synchronized immutable Microsoft Entra identity."
                )
            )
        email = user.entra_upn or user.email
        if not email:
            raise UserError(
                _("Every memo participant must have a synchronized UPN or email.")
            )
        return {
            "user_id": user.id,
            "name": user.name,
            "email": email,
            "entra_tenant_id": user.entra_tenant_id,
            "entra_object_id": user.entra_object_id,
        }

    def _create_signature_request(self, approval_lines, pdf_item, pdf_hash):
        self.ensure_one()
        recipients = []
        sequence = 10
        if self.memo_category_id.requester_signature_required:
            recipients.append(
                {
                    **self._recipient_identity(self.requester_id),
                    "sequence": sequence,
                    "participant_role": "requester",
                    "provider_role": "signer",
                    "required_widget_types": "signature,name,date",
                }
            )
            sequence += 10
        for line in approval_lines:
            is_final = line.participant_role == "final_signer"
            recipients.append(
                {
                    **self._recipient_identity(line.approver_user_id),
                    "sequence": sequence,
                    "participant_role": line.participant_role,
                    "provider_role": "signer" if is_final else "approver",
                    "required_widget_types": "signature,name,date"
                    if is_final
                    else False,
                }
            )
            sequence += 10
        emails = [item["email"].strip().lower() for item in recipients]
        if len(emails) != len(set(emails)):
            raise UserError(
                _("The memo route contains the same person more than once.")
            )
        route_digest = hashlib.sha256(
            json.dumps(
                [
                    (item["email"].lower(), item["participant_role"])
                    for item in recipients
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        idempotency_key = hashlib.sha256(
            f"memo|{self.id}|{pdf_hash}|{route_digest}".encode()
        ).hexdigest()
        existing = (
            self.env["lhi.opensign.request"]
            .sudo()
            .search([("idempotency_key", "=", idempotency_key)], limit=1)
        )
        if existing:
            self.sudo().write({"signature_request_id": existing.id})
            return existing
        previous = self.signature_request_ids.sorted("create_date", reverse=True)[:1]
        if previous and previous.status not in (
            "completed",
            "cancelled",
            "declined",
            "expired",
            "superseded",
        ):
            if (
                previous.provider_creation_uncertain
                and not previous.provider_request_id
            ):
                raise UserError(
                    _(
                        "The previous provider creation has an unknown outcome. "
                        "A Signature Administrator must resolve it before a new cycle."
                    )
                )
            previous.sudo().action_cancel()
        signatories = {
            "signatories": [
                {
                    "name": item["name"],
                    "email": item["email"],
                    "role": item["participant_role"],
                    "sequence": item["sequence"],
                }
                for item in recipients
            ]
        }
        signature_request = (
            self.env["lhi.opensign.request"]
            .sudo()
            .create(
                {
                    "name": f"{self.name} - Signature Cycle",
                    "memo_id": self.id,
                    "res_model": self._name,
                    "res_id": self.id,
                    "company_id": self.company_id.id,
                    "source_pdf_name": pdf_item.name,
                    "source_pdf_hash": pdf_hash,
                    "source_document_item_id": pdf_item.id,
                    "signatories": json.dumps(signatories),
                    "sequence_type": "sequential",
                    "expiry_date": self.expiry_date,
                    "idempotency_key": idempotency_key,
                    "supersedes_request_id": previous.id if previous else False,
                    "recipient_ids": [(0, 0, item) for item in recipients],
                }
            )
        )
        if previous:
            previous.sudo().write(
                {
                    "status": "superseded",
                    "superseded_by_request_id": signature_request.id,
                }
            )
        recipient_by_user = {
            recipient.user_id.id: recipient
            for recipient in signature_request.recipient_ids
            if recipient.participant_role != "requester"
        }
        for line in approval_lines:
            line.sudo().write(
                {
                    "signature_recipient_id": recipient_by_user[
                        line.approver_user_id.id
                    ].id
                }
            )
        self.sudo().write({"signature_request_id": signature_request.id})
        return signature_request

    def action_mark_ready(self):
        self.ensure_one()
        if self.requester_id != self.env.user:
            raise AccessError(_("Only the requester may finish authoring."))
        if self.state not in ("authoring", "returned", "failed"):
            raise UserError(_("This memo is not editable in Word."))
        if self.state != "authoring":
            self._transition("authoring")
        self._transition("ready_for_preparation")
        recipients = self.preparation_officer_ids or self.requester_id
        self._notify_users(
            recipients,
            _("Memo ready for signature preparation"),
            _("Memo %s is ready for dynamic signature-field preparation.") % self.name,
            schedule_activity=True,
        )
        return True

    def action_prepare_and_sign(self):
        self.ensure_one()
        self._ensure_requester_or_preparer()
        if self.state not in (
            "authoring",
            "ready_for_preparation",
            "returned",
            "failed",
        ):
            raise UserError(_("This memo is not ready for signature preparation."))
        try:
            pdf_item, pdf_hash = self._capture_current_pdf(
                retry_failed=self.state == "failed"
            )
            _approval_request, approval_lines = self._prepare_approval_route()
            signature_request = self._create_signature_request(
                approval_lines, pdf_item, pdf_hash
            )
            if self.state != "preparing":
                self._transition("preparing")
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            redirect_url = f"{base_url}/web#id={self.id}&model=lhi.memo&view_type=form"
            signature_request.sudo().action_create_provider_draft(
                redirect_url=redirect_url
            )
            self._notify_users(
                self.requester_id,
                _("Requester signature required"),
                _("Prepare the fields for memo %s, then sign and submit it.")
                % self.name,
                schedule_activity=True,
            )
            return {
                "type": "ir.actions.act_url",
                "url": f"/lhi/memo/{self.uuid}/prepare",
                "target": "new",
            }
        except Exception as error:
            return self._record_integration_failure("memo_preparation", error)

    def action_continue_preparation(self):
        self.ensure_one()
        self._ensure_requester_or_preparer()
        if not self.signature_request_id.provider_preparation_url:
            raise UserError(_("No secure preparation URL is available."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/memo/{self.uuid}/prepare",
            "target": "new",
        }

    def action_sign_and_submit(self):
        self.ensure_one()
        if self.requester_id != self.env.user:
            raise AccessError(_("Only the requester may sign and submit this memo."))
        signature_request = self.signature_request_id.sudo()
        if not signature_request.preparation_completed:
            signature_request.action_confirm_preparation()
            if self.state == "preparing":
                self._transition("requester_signature_pending")
        if not self.memo_category_id.requester_signature_required:
            self.approval_request_id.with_user(self.requester_id).action_activate()
            self._transition(
                "under_approval",
                {
                    "submitted_at": fields.Datetime.now(),
                    "current_approval_sequence": self._active_approver_lines()[
                        :1
                    ].sequence,
                },
            )
            self._notify_users(
                self.signature_request_id.current_recipient_id.user_id,
                _("Memo awaiting your action"),
                _("Memo %s is now awaiting your sequential approval.") % self.name,
                schedule_activity=True,
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Memo submitted"),
                    "message": _("The sequential approval route is now active."),
                    "type": "success",
                },
            }
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/memo/{self.uuid}/participant",
            "target": "new",
        }

    def action_approve(self):
        self.ensure_one()
        if not self._is_current_approver(self.env.user):
            raise AccessError(_("It is not your turn to approve this memo."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/memo/{self.uuid}/participant",
            "target": "new",
        }

    def _is_current_approver(self, user):
        self.ensure_one()
        current = self.signature_request_id.current_recipient_id
        return bool(
            current
            and current.user_id == user
            and current.participant_role != "requester"
        )

    def action_return_for_correction(self):
        self.ensure_one()
        if not self._is_current_approver(self.env.user):
            raise AccessError(_("It is not your turn to return this memo."))
        if not self.return_reason:
            raise UserError(_("Enter a return reason before returning the memo."))
        self.approval_request_id.with_user(self.env.user).action_return_for_correction(
            notes=self.return_reason
        )
        active_lines = self._active_approver_lines()
        current_line = active_lines.filtered(
            lambda line: (
                line.signature_recipient_id
                == self.signature_request_id.current_recipient_id
            )
        )[:1]
        (active_lines - current_line).sudo().write({"state": "superseded"})
        current_line.sudo().write(
            {
                "state": "returned",
                "acted_at": fields.Datetime.now(),
                "comments": self.return_reason,
            }
        )
        self.signature_request_id.sudo().action_supersede()
        self._transition(
            "returned",
            {
                "signature_request_id": False,
                "approval_request_id": False,
                "requester_signature_completed": False,
                "final_signature_completed": False,
                "current_approval_sequence": 0,
                "integration_error_code": False,
                "integration_error_message": False,
            },
        )
        self.message_post(
            body=_("Memo returned for correction: %s") % self.return_reason
        )
        self._notify_users(
            self.requester_id,
            _("Memo returned for correction"),
            _("Memo %s was returned. Correct the Word document and resubmit it.")
            % self.name,
            schedule_activity=True,
        )
        return True

    def action_reject(self):
        self.ensure_one()
        if not self._is_current_approver(self.env.user):
            raise AccessError(_("It is not your turn to reject this memo."))
        if not self.rejection_reason:
            raise UserError(_("Enter a rejection reason before rejecting the memo."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/memo/{self.uuid}/participant",
            "target": "new",
        }

    def action_withdraw(self):
        self.ensure_one()
        if self.requester_id != self.env.user:
            raise AccessError(_("Only the requester may withdraw this memo."))
        if self.state in TERMINAL_STATES or self.state == "completed":
            raise UserError(_("This memo can no longer be withdrawn."))
        if self.signature_request_id:
            self.signature_request_id.sudo().action_cancel()
        self._transition("cancelled")
        return True

    def action_retry_word_document(self):
        self.ensure_one()
        if self.requester_id != self.env.user and not self.env.user.has_group(
            "lhi_memo_management.group_lhi_memo_admin"
        ):
            raise AccessError(_("You cannot retry this memo document."))
        try:
            item = self._create_word_document(retry_failed=True)
            return self.action_open_word() if item else True
        except Exception as error:
            return self._record_integration_failure("sharepoint_word_retry", error)

    def action_refresh_document_status(self):
        self.ensure_one()
        if not self.source_docx_item_id:
            raise UserError(_("No SharePoint Word document exists yet."))
        self.source_docx_item_id.sudo().action_reconcile()
        if self.source_docx_item_id.storage_state == "available":
            self.sudo().write(
                {
                    "source_docx_web_url": self.source_docx_item_id.sharepoint_web_url,
                    "integration_error_code": False,
                    "integration_error_message": False,
                }
            )
        return True

    def action_refresh_provider_status(self):
        self.ensure_one()
        if not self.signature_request_id:
            raise UserError(_("No signature request exists."))
        self.signature_request_id.sudo().action_reconcile()
        return True

    def action_open_word(self):
        self.ensure_one()
        self._validate_before_opening_word()

        if not self.source_docx_item_id or self.source_docx_item_id.storage_state != "available":
            self._create_word_document_from_template()

        if not self.source_docx_web_url:
            raise UserError(_("The SharePoint Word document URL is not available."))

        self.source_docx_item_id.with_user(self.env.user).check_linked_access("read")
        return {
            "type": "ir.actions.act_url",
            "url": self.source_docx_web_url,
            "target": "new",
        }

    def _document_action(self, item):
        self.ensure_one()
        if not item or item.storage_state != "available":
            raise UserError(_("The requested SharePoint document is not available."))
        item.with_user(self.env.user).check_linked_access("read")
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/sharepoint/document/{item.uuid}/download",
            "target": "new",
        }

    def action_view_submitted_pdf(self):
        return self._document_action(self.source_pdf_item_id)

    def action_preview_document(self):
        self.ensure_one()
        if self.has_submitted_pdf:
            return self._document_action(self.source_pdf_item_id)
        return self.action_open_word()

    def action_view_signed_memo(self):
        return self._document_action(self.signed_pdf_item_id)

    def action_view_audit_certificate(self):
        return self._document_action(self.certificate_item_id)

    def action_track_approval(self):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("The approval route is not active."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Memo Approval"),
            "res_model": "lhi.approval.request",
            "res_id": self.approval_request_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _lhi_opensign_storage_target(self, field_name, suffix):
        self.ensure_one()
        filenames = {
            "signed_pdf": f"{self._safe_filename(self.name)}-Signed.pdf",
            "audit_certificate": f"{self._safe_filename(self.name)}-Audit-Certificate.pdf",
            "source_pdf": f"{self._safe_filename(self.name)}-Submitted.pdf",
        }
        requested_by = self.requester_id
        return {
            "linked_model": self._name,
            "linked_record_id": self.id,
            "linked_field": {
                "signed_pdf": "signed_pdf_item_id",
                "audit_certificate": "certificate_item_id",
                "source_pdf": "source_pdf_item_id",
            }[field_name],
            "requested_by": requested_by,
            "name": filenames[field_name],
        }

    def opensign_event_hook(self, request_id, event_type, payload):
        self.ensure_one()
        signature_request = self.env["lhi.opensign.request"].sudo().browse(request_id)
        if signature_request.memo_id != self:
            raise AccessError(_("The provider event does not belong to this memo."))
        recipient = signature_request._recipient_from_payload(payload)
        if event_type == "signed" and recipient:
            if recipient.participant_role == "requester":
                if self.requester_signature_completed:
                    return True
                self.approval_request_id.with_user(self.requester_id).action_activate()
                self._transition(
                    "under_approval",
                    {
                        "requester_signature_completed": True,
                        "requester_signed_at": recipient.completed_at
                        or fields.Datetime.now(),
                        "submitted_at": fields.Datetime.now(),
                        "current_approval_sequence": self._active_approver_lines()[
                            :1
                        ].sequence,
                    },
                )
                self.message_post(
                    body=_(
                        "Requester signature confirmed; sequential approval started."
                    )
                )
                next_user = signature_request.current_recipient_id.user_id
                self._notify_users(
                    next_user,
                    _("Memo awaiting your action"),
                    _("Memo %s is now awaiting your sequential approval.") % self.name,
                    schedule_activity=True,
                )
            else:
                line = self._active_approver_lines().filtered(
                    lambda item: item.signature_recipient_id == recipient
                )[:1]
                if not line:
                    raise UserError(
                        _("The provider participant is not in the memo approval route.")
                    )
                self.approval_request_id.with_user(recipient.user_id).action_approve(
                    notes=_("Approved through authenticated LHI Sign workflow.")
                )
                line.sudo().write(
                    {
                        "state": "approved",
                        "acted_at": recipient.completed_at or fields.Datetime.now(),
                        "comments": _("Provider-confirmed approval"),
                    }
                )
                pending = self._active_approver_lines().filtered(
                    lambda item: item.state == "pending"
                )
                vals = {
                    "current_approval_sequence": pending[:1].sequence if pending else 0,
                }
                if self.approval_request_id.state == "approved":
                    vals["approved_at"] = fields.Datetime.now()
                next_recipient = signature_request.current_recipient_id
                target = (
                    "final_signature_pending"
                    if next_recipient
                    and next_recipient.participant_role == "final_signer"
                    else self.state
                )
                if recipient.participant_role == "final_signer":
                    vals["final_signature_completed"] = True
                    vals["final_signed_at"] = (
                        recipient.completed_at or fields.Datetime.now()
                    )
                    target = "final_signature_pending"
                if target != self.state:
                    self._transition(target, vals)
                else:
                    self.sudo().write(vals)
                next_recipient = signature_request.current_recipient_id
                if next_recipient:
                    self._notify_users(
                        next_recipient.user_id,
                        _("Memo awaiting your action"),
                        (
                            _("Memo %s is ready for your final signature.")
                            if next_recipient.participant_role == "final_signer"
                            else _("Memo %s is ready for your approval.")
                        )
                        % self.name,
                        schedule_activity=True,
                    )
        elif event_type == "declined":
            reason = (
                payload.get("declineReason")
                or payload.get("reason")
                or _("Declined in LHI Sign")
            )
            if self.approval_request_id.state == "under_review" and recipient:
                self.approval_request_id.with_user(recipient.user_id).action_reject(
                    notes=reason
                )
            self._transition("rejected", {"rejection_reason": reason})
            self._notify_users(
                self.requester_id,
                _("Memo rejected"),
                _("Memo %s was rejected. Review the recorded reason.") % self.name,
                schedule_activity=True,
            )
        elif event_type == "revoked" and self.state not in TERMINAL_STATES:
            self._transition("cancelled")
        return True

    def opensign_completed_hook(self, request_id):
        self.ensure_one()
        if self.state == "completed":
            return True
        signature_request = self.env["lhi.opensign.request"].sudo().browse(request_id)
        if signature_request.memo_id != self:
            raise AccessError(
                _("The completed provider request does not belong to this memo.")
            )
        if self.approval_request_id.state != "approved":
            raise UserError(
                _("The provider completed before the Odoo approval route completed.")
            )
        if (
            not signature_request.signed_stored
            or not signature_request.certificate_stored
        ):
            raise UserError(
                _("SharePoint has not confirmed the completed signature artefacts.")
            )
        self._transition(
            "completed",
            {
                "signed_pdf_item_id": signature_request.signed_document_item_id.id,
                "signed_pdf_hash": signature_request.signed_pdf_hash,
                "certificate_item_id": signature_request.certificate_document_item_id.id,
                "final_signature_completed": True,
                "final_signed_at": self.final_signed_at or fields.Datetime.now(),
                "completed_at": fields.Datetime.now(),
                "integration_error_code": False,
                "integration_error_message": False,
            },
        )
        self.message_post(
            body=_("Signed memo and audit certificate confirmed in SharePoint.")
        )
        participants = (
            self.requester_id
            | self.recipient_user_ids
            | self.approver_line_ids.mapped("approver_user_id")
        )
        self._notify_users(
            participants,
            _("Memo completed"),
            _("Memo %s is complete; its signed PDF and certificate are in SharePoint.")
            % self.name,
        )
        return True

    @api.model
    def cron_expire_memos(self, batch_size=100):
        now = fields.Datetime.now()
        memos = self.sudo().search(
            [
                ("expiry_date", "<=", now),
                ("state", "not in", list(TERMINAL_STATES | {"completed"})),
            ],
            limit=min(max(int(batch_size), 1), 500),
        )
        for memo in memos:
            if memo.signature_request_id:
                try:
                    memo.signature_request_id.action_cancel()
                except Exception as error:
                    memo._record_integration_failure("provider_expiry_cancel", error)
                    continue
            memo._transition("expired")
            memo.message_post(body=_("Memo expired before completion."))
            memo._notify_users(
                memo.requester_id | memo.current_recipient_id.user_id,
                _("Memo expired"),
                _("Memo %s expired before completion.") % memo.name,
            )
        return True
