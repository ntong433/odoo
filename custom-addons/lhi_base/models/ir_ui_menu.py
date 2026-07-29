from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _load_menus_blacklist(self):
        """Hide an installed HR application without requiring the HR addon.

        LHI ERP is intentionally employee-record independent.  Looking up the
        optional XML ID at runtime keeps a clean HR-free database installable
        while also hiding the complete HR tree when another legacy module still
        requires HR to remain technically installed.
        """
        blacklisted = set(super()._load_menus_blacklist())
        hr_root = self.env.ref("hr.menu_hr_root", raise_if_not_found=False)
        if hr_root:
            hr_menus = self.with_context(active_test=False).search(
                [("id", "child_of", hr_root.id)]
            )
            blacklisted.update(hr_menus.ids)
        return sorted(blacklisted)
