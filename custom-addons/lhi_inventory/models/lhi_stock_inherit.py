# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StockMove(models.Model):
    _inherit = 'stock.move'

    lhi_project_id = fields.Many2one('lhi.project', string='Project Allocation')
    lhi_donor_id = fields.Many2one('res.partner', string='Donor Ownership')
    lhi_activity_id = fields.Many2one('lhi.workplan.activity', string='Activity Usage')
    
    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        vals['lhi_project_id'] = self.lhi_project_id.id
        vals['lhi_donor_id'] = self.lhi_donor_id.id
        return vals

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    lhi_project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    lhi_donor_id = fields.Many2one('res.partner', string='Donor', tracking=True)
    
class StockQuant(models.Model):
    _inherit = 'stock.quant'

    lhi_project_id = fields.Many2one('lhi.project', string='Project Ownership')
    lhi_donor_id = fields.Many2one('res.partner', string='Donor Ownership')
    
    @api.model_create_multi
    def create(self, vals_list):
        # Allow inheriting project/donor from moves when quants are created
        return super(StockQuant, self).create(vals_list)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    lhi_project_id = fields.Many2one(related='move_id.lhi_project_id', store=True)
    lhi_donor_id = fields.Many2one(related='move_id.lhi_donor_id', store=True)
