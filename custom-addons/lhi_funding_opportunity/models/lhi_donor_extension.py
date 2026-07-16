# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiDonor(models.Model):
    _inherit = 'lhi.donor'

    opportunity_count = fields.Integer(string='Opportunities', compute='_compute_opportunity_count')

    def _compute_opportunity_count(self):
        for record in self:
            record.opportunity_count = self.env['lhi.funding.opportunity'].search_count([
                ('donor_id', '=', record.id)
            ])
            
    def action_view_opportunities(self):
        self.ensure_one()
        return {
            'name': 'Funding Opportunities',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.funding.opportunity',
            'view_mode': 'kanban,list,form',
            'domain': [('donor_id', '=', self.id)],
            'context': {'default_donor_id': self.id}
        }
