from odoo import models


class ResGroups(models.Model):
    _inherit = "res.groups"

    def _lhi_entra_protected_groups(self):
        protected = super()._lhi_entra_protected_groups()
        for xmlid in (
            "lhi_signature_bridge.group_lhi_signature_admin",
            "lhi_signature_bridge.group_lhi_signature_preparation_officer",
        ):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                protected |= group
        return protected
