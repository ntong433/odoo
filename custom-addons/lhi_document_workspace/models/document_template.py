import os
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class LhiDocumentTemplate(models.Model):
    _name = "lhi.document.template"
    _description = "Approved SharePoint Office Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    graph_connection_id = fields.Many2one(
        "lhi.graph.connection", required=True, ondelete="restrict", index=True
    )
    model_name = fields.Char(required=True, index=True)
    file_type = fields.Selection(
        [
            ("word", "Microsoft Word"),
            ("excel", "Microsoft Excel"),
            ("powerpoint", "Microsoft PowerPoint"),
        ],
        required=True,
    )
    source_drive_id = fields.Char(required=True, groups="lhi_security.group_lhi_erp_admin")
    source_item_id = fields.Char(required=True, groups="lhi_security.group_lhi_erp_admin")
    source_name = fields.Char(readonly=True)
    source_mime_type = fields.Char(readonly=True)
    source_size = fields.Integer(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("invalid", "Invalid"),
            ("disabled", "Disabled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    validated_at = fields.Datetime(readonly=True)
    validated_by_id = fields.Many2one("res.users", readonly=True)
    last_error = fields.Text(readonly=True)

    _template_source_unique = models.Constraint(
        "unique(company_id, model_name, source_drive_id, source_item_id)",
        "This SharePoint template is already configured for the business model.",
    )

    @api.constrains("model_name")
    def _check_model_name(self):
        for template in self:
            if template.model_name not in self.env:
                raise ValidationError(_("The template business model does not exist."))

    @api.constrains("source_name", "file_type")
    def _check_source_extension(self):
        allowed = {
            "word": {"doc", "docx"},
            "excel": {"xls", "xlsx"},
            "powerpoint": {"ppt", "pptx"},
        }
        for template in self.filtered("source_name"):
            extension = os.path.splitext(template.source_name)[1].lower().lstrip(".")
            if extension not in allowed[template.file_type]:
                raise ValidationError(
                    _("The SharePoint template extension does not match its Office type.")
                )

    def action_validate_and_approve(self):
        self.check_access("write")
        for template in self:
            try:
                payload = template.graph_connection_id.graph_request(
                    "GET",
                    (
                        f"/drives/{quote(template.source_drive_id)}/items/"
                        f"{quote(template.source_item_id)}"
                    ),
                    auth_context="application",
                    params={
                        "$select": "id,name,size,file,parentReference,lastModifiedDateTime"
                    },
                )
                if payload.get("id") != template.source_item_id or not payload.get("file"):
                    raise UserError(_("The configured SharePoint item is not a file."))
                template.sudo().write(
                    {
                        "source_name": payload.get("name"),
                        "source_mime_type": (payload.get("file") or {}).get("mimeType"),
                        "source_size": int(payload.get("size") or 0),
                        "state": "approved",
                        "validated_at": fields.Datetime.now(),
                        "validated_by_id": self.env.user.id,
                        "last_error": False,
                    }
                )
                template._check_source_extension()
            except Exception as error:
                safe = template.graph_connection_id._redact_text(str(error))[:2000]
                template.sudo().write({"state": "invalid", "last_error": safe})
                raise
        return True

    def action_disable(self):
        self.check_access("write")
        self.write({"state": "disabled", "active": False})
        return True
