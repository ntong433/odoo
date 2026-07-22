from odoo import models


class ResGroups(models.Model):
    _inherit = "res.groups"

    def _lhi_entra_protected_groups(self):
        protected = super()._lhi_entra_protected_groups()
        memo_admin = self.env.ref(
            "lhi_memo_management.group_lhi_memo_admin", raise_if_not_found=False
        )
        return protected | memo_admin if memo_admin else protected
