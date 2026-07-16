import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiGraphLibrary(models.Model):
    _name = "lhi.graph.library"
    _description = "Configured SharePoint Document Library"
    _order = "sequence, id"

    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="connection_id.company_id",
        store=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    code = fields.Selection(
        [
            ("projects", "Projects"),
            ("procurement", "Procurement"),
            ("operations", "Operations"),
            ("controlled_documents", "Controlled Documents"),
            ("signed_documents", "Signed Documents"),
        ],
        required=True,
        index=True,
    )
    expected_name = fields.Char(required=True)
    configured_drive_id = fields.Char(
        string="Candidate Drive ID",
        help="Optional candidate. It is not authoritative until Graph validation succeeds.",
    )
    drive_id = fields.Char(
        string="Validated Drive ID",
        readonly=True,
        copy=False,
        index=True,
    )
    drive_web_url = fields.Char(readonly=True, copy=False)
    root_item_id = fields.Char(readonly=True, copy=False)
    validation_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("valid", "Validated"),
            ("invalid", "Invalid"),
        ],
        default="pending",
        required=True,
        readonly=True,
        copy=False,
    )
    last_validated_at = fields.Datetime(readonly=True, copy=False)
    validation_message = fields.Text(readonly=True, copy=False)

    _connection_code_unique = models.Constraint(
        "unique(connection_id, code)",
        "Each SharePoint library role can be configured once per connection.",
    )

    @api.constrains("configured_drive_id")
    def _check_candidate_drive_id(self):
        for record in self:
            value = record.configured_drive_id
            if value and (len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9!._~-]+", value)):
                raise ValidationError(_("The candidate Drive ID has an invalid format."))

    def write(self, vals):
        protected = {
            "drive_id",
            "drive_web_url",
            "root_item_id",
            "validation_state",
            "last_validated_at",
            "validation_message",
        }
        if protected.intersection(vals) and not self.env.context.get("lhi_graph_validated_write"):
            raise ValidationError(
                _("Validated SharePoint identifiers can only be written after a Graph validation.")
            )
        if {"expected_name", "configured_drive_id"}.intersection(vals):
            vals = dict(vals)
            vals.update(
                {
                    "drive_id": False,
                    "drive_web_url": False,
                    "root_item_id": False,
                    "validation_state": "pending",
                    "last_validated_at": False,
                    "validation_message": False,
                }
            )
            return super(
                LhiGraphLibrary,
                self.with_context(lhi_graph_validated_write=True),
            ).write(vals)
        return super().write(vals)

    def action_validate(self):
        self.ensure_one()
        return self.connection_id._validate_library(self)

