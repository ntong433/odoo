from odoo import api, fields, models


PROTECTED_GROUP_XMLIDS = (
    "base.group_system",
    "base.group_erp_manager",
    "lhi_security.group_lhi_erp_admin",
    "lhi_security.group_lhi_integration_service",
    "lhi_security.group_lhi_internal_auditor",
    "lhi_accounting_base.group_lhi_accounting_sandbox",
)


class ResGroups(models.Model):
    _inherit = "res.groups"

    lhi_entra_management_mode = fields.Selection(
        [
            ("unmapped", "Unmapped"),
            ("entra", "Entra-managed"),
            ("odoo", "Odoo-managed"),
            ("hybrid", "Hybrid"),
            ("protected", "Protected"),
        ],
        compute="_compute_lhi_entra_classification",
        string="Entra Ownership",
    )
    lhi_entra_mapping_count = fields.Integer(
        compute="_compute_lhi_entra_classification",
        string="Entra Mapping Count",
    )

    @api.depends_context("company")
    def _compute_lhi_entra_classification(self):
        protected = self._lhi_entra_protected_groups()
        mappings = self.env["lhi.entra.group.mapping"].sudo().search(
            [
                ("company_id", "in", self.env.companies.ids),
                ("odoo_group_id", "in", self.ids),
                ("enabled", "=", True),
            ]
        )
        by_group = {}
        for mapping in mappings:
            by_group.setdefault(mapping.odoo_group_id.id, []).append(mapping)
        for group in self:
            group_mappings = by_group.get(group.id, [])
            group.lhi_entra_mapping_count = len(group_mappings)
            if group in protected:
                group.lhi_entra_management_mode = "protected"
            elif group_mappings:
                group.lhi_entra_management_mode = group_mappings[0].management_mode
            else:
                group.lhi_entra_management_mode = "unmapped"

    @api.model
    def _lhi_entra_protected_groups(self):
        groups = self.browse()
        for xmlid in PROTECTED_GROUP_XMLIDS:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record and record._name == "res.groups":
                groups |= record
        return groups

    def _lhi_entra_effective_groups(self):
        return self | self.mapped("all_implied_ids")
