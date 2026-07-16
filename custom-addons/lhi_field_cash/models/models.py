# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiFieldCashbook(models.Model):
    _name = 'lhi.field.cashbook'
    _description = 'Field Cashbook'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Cashbook Name', required=True)
    custodian_id = fields.Many2one('res.users', string='Custodian', required=True)
    location_id = fields.Char(string='Field Office')
    
    balance = fields.Monetary(string='Current Balance', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    max_limit = fields.Monetary(string='Maximum Limit', currency_field='currency_id')
    
    state = fields.Selection([
        ('active', 'Active'),
        ('reconciling', 'Reconciling'),
        ('locked', 'Locked')
    ], string='Status', default='active', tracking=True)
    
    def action_start_reconciliation(self):
        self.state = 'reconciling'
        
    def action_complete_reconciliation(self):
        self.state = 'active'
