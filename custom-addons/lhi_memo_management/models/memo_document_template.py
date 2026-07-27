# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiMemoDocumentTemplate(models.Model):
    _name = "lhi.memo.document.template"
    _description = "LHI Memo Document Template Configuration"
    _order = "is_default desc, name, id"

    name = fields.Char(string="Template Name", required=True, tracking=True)
    code = fields.Char(string="Template Code", required=True, index=True)
    version = fields.Char(string="Business Version", required=True, default="1.0")
    sharepoint_version = fields.Char(string="SharePoint Version", required=True, default="1.0")

    sharepoint_drive_id = fields.Char(string="SharePoint Drive ID", tracking=True)
    sharepoint_item_id = fields.Char(string="SharePoint File Item ID", tracking=True)
    sharepoint_parent_folder_id = fields.Char(string="SharePoint Parent Folder ID")
    sharepoint_site_id = fields.Char(string="SharePoint Site ID")
    sharepoint_web_url = fields.Char(string="SharePoint Web URL")
    sharepoint_etag = fields.Char(string="SharePoint ETag")
    sharepoint_ctag = fields.Char(string="SharePoint CTag")
    sharepoint_file_name = fields.Char(string="Template File Name")
    sharepoint_file_size = fields.Integer(string="File Size (Bytes)")
    sharepoint_last_modified = fields.Datetime(string="SharePoint Last Modified")

    is_default = fields.Boolean(string="Default Template", default=False, tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    notes = fields.Text(string="Notes")

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "The template code must be unique per company."),
    ]

    @api.constrains("is_default", "active", "company_id")
    def _check_default_template_unique(self):
        for record in self:
            if record.is_default:
                if not record.active:
                    raise ValidationError(_("Inactive templates cannot be marked as default."))
                domain = [
                    ("is_default", "=", True),
                    ("active", "=", True),
                    ("company_id", "=", record.company_id.id),
                    ("id", "!=", record.id),
                ]
                existing = self.search_count(domain)
                if existing > 0:
                    raise ValidationError(
                        _("Only one active default memo template is allowed per company.")
                    )

    @api.constrains("active", "sharepoint_drive_id", "sharepoint_item_id", "version")
    def _check_active_template_requirements(self):
        for record in self:
            if record.active:
                if not record.sharepoint_drive_id:
                    raise ValidationError(_("SharePoint Drive ID is required for an active template."))
                if not record.sharepoint_item_id:
                    raise ValidationError(_("SharePoint File Item ID is required for an active template."))
                if not record.version:
                    raise ValidationError(_("Template version is required."))
