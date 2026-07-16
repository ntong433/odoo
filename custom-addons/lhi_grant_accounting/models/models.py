# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    lhi_donor_id = fields.Many2one('res.partner', string='Donor', domain=[('is_company', '=', True)])
    lhi_award_id = fields.Char(string='Award ID')
    lhi_project_id = fields.Char(string='Project ID')
    lhi_output_id = fields.Char(string='Output Code')
    lhi_activity_id = fields.Char(string='Activity Code')
    lhi_funding_source_id = fields.Char(string='Funding Source')
    lhi_department_id = fields.Many2one('hr.department', string='Department')
    lhi_cost_centre_id = fields.Char(string='Cost Centre')
    lhi_location_id = fields.Char(string='Location Dimension')
    
    lhi_restriction_type = fields.Selection([
        ('unrestricted', 'Unrestricted'),
        ('temporarily_restricted', 'Temporarily Restricted'),
        ('permanently_restricted', 'Permanently Restricted')
    ], string='Donor Restriction', default='unrestricted')

    @api.constrains('lhi_donor_id', 'lhi_restriction_type')
    def _check_restrictions(self):
        for record in self:
            if record.lhi_restriction_type != 'unrestricted' and not record.lhi_donor_id:
                raise ValidationError(_("A donor must be specified for restricted funds."))
