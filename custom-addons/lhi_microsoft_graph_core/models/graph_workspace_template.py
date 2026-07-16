import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiGraphWorkspaceTemplate(models.Model):
    _name = "lhi.graph.workspace.template"
    _description = "SharePoint Workspace Folder Template"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
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
    description = fields.Text(translate=True)
    line_ids = fields.One2many(
        "lhi.graph.workspace.template.line",
        "template_id",
        string="Folders",
        copy=True,
    )

    _code_unique = models.Constraint(
        "unique(code)",
        "A SharePoint workspace template code must be unique.",
    )

    @api.constrains("code")
    def _check_code(self):
        for record in self:
            if not re.fullmatch(r"[a-z0-9_]+", record.code or ""):
                raise ValidationError(_("Template codes must use lowercase letters, numbers, and underscores."))


class LhiGraphWorkspaceTemplateLine(models.Model):
    _name = "lhi.graph.workspace.template.line"
    _description = "SharePoint Workspace Folder Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "lhi.graph.workspace.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    relative_path = fields.Char(required=True)

    _template_path_unique = models.Constraint(
        "unique(template_id, relative_path)",
        "A folder path can appear only once in a workspace template.",
    )

    @api.constrains("relative_path")
    def _check_relative_path(self):
        forbidden = set('"*:<>?/\\|')
        for record in self:
            path = (record.relative_path or "").strip()
            if (
                not path
                or path.startswith(("/", "\\"))
                or ".." in path.split("/")
                or any(character in forbidden for character in path)
            ):
                raise ValidationError(_("The SharePoint folder template contains an unsafe path."))

