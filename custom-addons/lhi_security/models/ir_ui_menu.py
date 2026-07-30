# -*- coding: utf-8 -*-
from odoo import models, api


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Return all active menu IDs for protected administrator without group/ACL filtering."""
        if self.env.user._lhi_is_protected_administrator():
            active_menus = self.with_context({}).search([('active', '=', True)])
            return frozenset(active_menus.ids)
        return super()._visible_menu_ids(debug=debug)
