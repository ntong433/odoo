# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiBid(models.Model):
    _name = 'lhi.bid'
    _description = 'Procurement Bid'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sourcing_id = fields.Many2one('lhi.sourcing', string='Sourcing Event', required=True, ondelete='cascade')
    vendor_id = fields.Many2one('lhi.vendor', string='Vendor', required=True, tracking=True)
    
    technical_compliant = fields.Boolean(string='Technically Compliant', default=False, tracking=True)
    technical_score = fields.Float(string='Technical Score (out of 100)', tracking=True)
    
    financial_amount = fields.Monetary(string='Financial Bid Amount', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(related='sourcing_id.currency_id', store=True)
    
    financial_score = fields.Float(string='Financial Score (Calculated)', readonly=True)
    weighted_score = fields.Float(string='Weighted Final Score', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('disqualified', 'Disqualified'),
        ('recommended', 'Recommended'),
        ('awarded', 'Awarded')
    ], string='Status', default='draft', tracking=True)
    
    disqualification_reason = fields.Text(string='Disqualification Reason', tracking=True)
    evaluator_comments = fields.Text(string='Evaluator Comments', tracking=True)
    
    company_id = fields.Many2one(related='sourcing_id.company_id', store=True)

    def action_submit(self):
        self.write({'state': 'submitted'})
        self.sourcing_id._log_audit(f"Bid submitted by {self.vendor_id.name}.")

    def action_disqualify(self):
        self.write({'state': 'disqualified'})
        self.sourcing_id._log_audit(f"Bid by {self.vendor_id.name} disqualified. Reason: {self.disqualification_reason}")
