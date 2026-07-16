import json
import os
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiDocumentStoragePolicy(models.Model):
    _name = "lhi.document.storage.policy"
    _description = "LHI Document Storage Policy"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", index=True)
    model_name = fields.Char(required=True, index=True)
    field_name = fields.Char(
        index=True,
        help="Optional attachment or binary field. Empty applies to all attachments on the model.",
    )
    storage_backend = fields.Selection(
        [("sharepoint", "SharePoint Online"), ("odoo", "Odoo Technical Storage")],
        default="sharepoint",
        required=True,
    )
    library_code = fields.Selection(
        [
            ("projects", "Projects"),
            ("procurement", "Procurement"),
            ("operations", "Operations"),
            ("controlled_documents", "Controlled Documents"),
            ("signed_documents", "Signed Documents"),
        ],
        required=True,
    )
    folder_strategy = fields.Selection(
        [
            ("library_root", "Library Root"),
            ("fixed_path", "Fixed Path"),
            ("model_record", "Model / Record"),
            ("project_workspace", "Project Workspace"),
        ],
        default="model_record",
        required=True,
    )
    fixed_folder_path = fields.Char()
    project_subfolder = fields.Selection(
        [
            ("01 Proposal", "01 Proposal"),
            ("02 Award and Agreement", "02 Award and Agreement"),
            ("03 Workplans", "03 Workplans"),
            ("04 MEAL and Evidence", "04 MEAL and Evidence"),
            ("05 Procurement", "05 Procurement"),
            ("06 Reports", "06 Reports"),
            ("07 Partners", "07 Partners"),
            ("08 Compliance and Audit", "08 Compliance and Audit"),
            ("09 Closeout", "09 Closeout"),
        ]
    )
    maximum_size_mb = fields.Integer(default=250, required=True)
    small_upload_limit_mb = fields.Integer(default=16, required=True)
    upload_chunk_size_kb = fields.Integer(default=10240, required=True)
    allowed_extensions = fields.Char(
        default="pdf,doc,docx,xls,xlsx,ppt,pptx,csv,txt,png,jpg,jpeg,tif,tiff,zip"
    )
    required_metadata_json = fields.Text(default="{}")
    retention_category = fields.Char()
    document_category = fields.Char()
    confidentiality = fields.Selection(
        [
            ("internal", "Internal"),
            ("confidential", "Confidential"),
            ("restricted", "Restricted"),
        ],
        default="internal",
        required=True,
    )
    conflict_behavior = fields.Selection(
        [("fail", "Fail"), ("rename", "Rename"), ("replace", "Replace")],
        default="fail",
        required=True,
    )
    direct_browser_upload = fields.Boolean(default=True)

    _model_field_company_unique = models.Constraint(
        "unique(model_name, field_name, company_id)",
        "A storage policy already exists for this model, field, and company.",
    )

    @api.constrains(
        "model_name",
        "field_name",
        "maximum_size_mb",
        "small_upload_limit_mb",
        "upload_chunk_size_kb",
        "required_metadata_json",
    )
    def _check_policy(self):
        for policy in self:
            if not re.fullmatch(r"[a-z0-9_.]+", policy.model_name or ""):
                raise ValidationError(_("The policy model name is invalid."))
            if policy.field_name and not re.fullmatch(r"[a-zA-Z0-9_]+", policy.field_name):
                raise ValidationError(_("The policy field name is invalid."))
            if policy.maximum_size_mb <= 0 or policy.maximum_size_mb > 15360:
                raise ValidationError(_("Maximum file size must be between 1 MB and 15 GB."))
            if not 1 <= policy.small_upload_limit_mb <= 250:
                raise ValidationError(_("Small upload limit must be between 1 MB and 250 MB."))
            if policy.upload_chunk_size_kb <= 0 or policy.upload_chunk_size_kb % 320:
                raise ValidationError(
                    _("Upload chunk size must be a positive multiple of 320 KiB.")
                )
            if policy.upload_chunk_size_kb >= 60 * 1024:
                raise ValidationError(_("Upload chunks must be smaller than 60 MiB."))
            try:
                value = json.loads(policy.required_metadata_json or "{}")
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Required metadata must be valid JSON.")) from error
            if not isinstance(value, dict):
                raise ValidationError(_("Required metadata JSON must be an object."))

    def allowed_extension_set(self):
        self.ensure_one()
        return {
            value.strip().lower().lstrip(".")
            for value in (self.allowed_extensions or "").split(",")
            if value.strip()
        }

    def validate_file(self, name, size):
        self.ensure_one()
        if size <= 0:
            raise ValidationError(_("Empty business documents cannot be uploaded."))
        if size > self.maximum_size_mb * 1024 * 1024:
            raise ValidationError(
                _("The file exceeds the %s MB storage-policy limit.")
                % self.maximum_size_mb
            )
        extension = os.path.splitext(name or "")[1].lower().lstrip(".")
        allowed = self.allowed_extension_set()
        if allowed and extension not in allowed:
            raise ValidationError(
                _("Files with the .%s extension are not allowed by this storage policy.")
                % (extension or _("(none)"))
            )

    @api.model
    def resolve_policy(self, model_name, field_name=False, company=None):
        company = company or self.env.company
        base_domain = [
            ("active", "=", True),
            ("model_name", "=", model_name),
            ("company_id", "in", [False, company.id]),
        ]
        if field_name:
            exact = self.sudo().search(
                base_domain + [("field_name", "=", field_name)],
                order="company_id desc, sequence, id",
                limit=1,
            )
            if exact:
                return exact
        return self.sudo().search(
            base_domain + [("field_name", "=", False)],
            order="company_id desc, sequence, id",
            limit=1,
        )

