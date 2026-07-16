# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiPurchaseRequestInheritProcurement(models.Model):
    _inherit = 'lhi.purchase.request'

    sourcing_id = fields.Many2one('lhi.sourcing', string='Sourcing Event', readonly=True)

    def action_create_sourcing_event(self):
        for req in self:
            sourcing = self.env['lhi.sourcing'].create({
                'title': f'Sourcing for PR {req.name}',
                'request_id': req.id,
                'sourcing_type': req.procurement_method,
            })
            req.sourcing_id = sourcing.id
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sourcing Event',
                'res_model': 'lhi.sourcing',
                'res_id': sourcing.id,
                'view_mode': 'form',
                'target': 'current',
            }
