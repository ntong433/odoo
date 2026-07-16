# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiDonor(models.Model):
    _inherit = 'lhi.donor'

    # Enhancing Donor with comprehensive CRM/relationship fields
    partner_id = fields.Many2one('res.partner', string='Related Partner', 
                                 help="Link to the standard Odoo Contact/Partner for invoicing and address.")
    contact_ids = fields.One2many('res.partner', 'parent_id', string='Donor Contacts',
                                  domain=[('is_company', '=', False)],
                                  help="Specific individuals working at this donor.")
    
    strategic_focus_ids = fields.Many2many('lhi.sector', string='Strategic Focus Sectors')
    geography_ids = fields.Many2many('lhi.office', string='Geographic Focus')
    
    past_performance_score = fields.Integer(string='Past Performance Score (1-100)', tracking=True)
    compliance_requirements = fields.Text(string='Compliance & Reporting Requirements')
    
    # We can automatically compute the number of opportunities later from lhi_funding_opportunity
    opportunity_count = fields.Integer(string='Opportunities', compute='_compute_opportunity_count')

    def _compute_opportunity_count(self):
        for record in self:
            # This will be overridden or computed when lhi_funding_opportunity is installed.
            record.opportunity_count = 0

    def action_view_opportunities(self):
        self.ensure_one()
        return False
