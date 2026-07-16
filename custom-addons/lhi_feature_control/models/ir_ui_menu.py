# -*- coding: utf-8 -*-
from odoo import models, api

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        res = super(IrUiMenu, self).search(args, offset=offset, limit=limit, order=order)
        if not self.env['lhi.feature.flag'].is_flag_enabled('lhi_accounting_enabled'):
            # Fetch all menu record IDs belonging to the account module
            acc_menus = self.env['ir.model.data'].sudo().search([
                ('module', '=', 'account'),
                ('model', '=', 'ir.ui.menu')
            ]).mapped('res_id')
            if acc_menus:
                res = res.filtered(lambda m: m.id not in acc_menus)
        return res
