# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiAwardExtension(models.Model):
    _inherit = 'lhi.award'

    donor_id = fields.Many2one('lhi.donor', string='Donor', tracking=True)
    agreement_date = fields.Date(string='Agreement Signature Date', tracking=True)
    closeout_period_days = fields.Integer(string='Closeout Period (Days)', default=90)
    
    reporting_currency_id = fields.Many2one('res.currency', string='Reporting Currency', tracking=True)
    
    agreement_document_id = fields.Many2one('ir.attachment', string='Signed Agreement Document')
    
    # Conditions and Restrictions
    indirect_cost_rule = fields.Text(string='Indirect Cost Rules')
    cost_share = fields.Text(string='Cost Share Requirements')
    procurement_thresholds = fields.Text(string='Procurement Thresholds')
    reporting_requirements = fields.Text(string='Reporting Requirements')
    audit_requirements = fields.Text(string='Audit Requirements')
    branding = fields.Text(string='Branding & Visibility')
    safeguarding = fields.Text(string='Safeguarding')
    data_protection = fields.Text(string='Data Protection')
    asset_ownership = fields.Text(string='Asset Ownership & Disposition')
    record_retention = fields.Text(string='Record Retention')
    special_conditions = fields.Text(string='Special Conditions / Exchange Rate Policy')

