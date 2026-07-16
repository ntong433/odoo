import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiEntraGroupMapping(models.Model):
    _name = "lhi.entra.group.mapping"
    _description = "Entra Group to Existing Odoo Group Mapping"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority, id"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        check_company=True,
        ondelete="restrict",
        tracking=True,
    )
    entra_group_object_id = fields.Char(
        string="Entra Group Object ID",
        required=True,
        index=True,
        copy=False,
        tracking=True,
    )
    entra_group_display_name = fields.Char(
        string="Entra Group Display Name",
        tracking=True,
    )
    odoo_group_id = fields.Many2one(
        "res.groups",
        string="Existing Odoo Group",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    management_mode = fields.Selection(
        [
            ("entra", "Entra-managed"),
            ("odoo", "Odoo-managed"),
            ("hybrid", "Hybrid"),
            ("protected", "Protected"),
        ],
        required=True,
        default="hybrid",
        tracking=True,
    )
    priority = fields.Integer(default=100, required=True, index=True)
    conflict_policy = fields.Selection(
        [
            ("block", "Block Conflicting Change"),
            ("preserve", "Preserve Current Membership"),
            ("review", "Require Administrator Review"),
        ],
        default="block",
        required=True,
        tracking=True,
    )
    enabled = fields.Boolean(default=True, tracking=True)
    last_seen_at = fields.Datetime(readonly=True, copy=False)

    _entra_group_unique = models.Constraint(
        "unique(connection_id, entra_group_object_id)",
        "An Entra group can be mapped only once per Microsoft Graph connection.",
    )
    _odoo_group_unique = models.Constraint(
        "unique(connection_id, odoo_group_id)",
        "An existing Odoo group can have only one Entra mapping per connection.",
    )

    @api.depends("entra_group_display_name", "odoo_group_id")
    def _compute_name(self):
        for record in self:
            record.name = "%s → %s" % (
                record.entra_group_display_name or record.entra_group_object_id or _("Entra Group"),
                record.odoo_group_id.display_name or _("Odoo Group"),
            )

    @api.constrains("entra_group_object_id")
    def _check_entra_group_object_id(self):
        for record in self:
            try:
                uuid.UUID(record.entra_group_object_id or "")
            except (ValueError, AttributeError, TypeError) as error:
                raise ValidationError(_("The Entra group object ID must be a UUID.")) from error

    @api.constrains("odoo_group_id", "management_mode")
    def _check_protected_group_mapping(self):
        protected = self.env["res.groups"]._lhi_entra_protected_groups()
        for record in self:
            if record.odoo_group_id in protected and record.management_mode != "protected":
                raise ValidationError(
                    _(
                        "Protected Odoo groups may only be classified as Protected. "
                        "Entra synchronization can never grant or remove them."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._audit_mapping_change(_("Entra group mapping created."))
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals:
            self._audit_mapping_change(
                _("Entra group mapping changed: %s") % ", ".join(sorted(vals))
            )
        return result

    def unlink(self):
        self._audit_mapping_change(_("Entra group mapping deleted."))
        return super().unlink()

    def _audit_mapping_change(self, description):
        for record in self:
            self.env["lhi.audit.log"].create_event(
                event_type="permission_change",
                res_model=record._name,
                res_id=record.id,
                description=description,
            )

