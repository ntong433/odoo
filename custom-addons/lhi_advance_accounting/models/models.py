# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiStaffAdvance(models.Model):
    _name = 'lhi.staff.advance'
    _description = 'Staff Advance Accounting'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Advance Ref', required=True, copy=False, default='New')
    user_id = fields.Many2one('res.users', string='Staff Member', default=lambda self: self.env.user, required=True)
    amount = fields.Monetary(string='Amount Requested', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('retired', 'Retired'),
        ('refunded', 'Refunded')
    ], string='Status', default='draft', tracking=True)
    
    payment_move_id = fields.Many2one('account.move', string='Payment Entry')
    retirement_move_id = fields.Many2one('account.move', string='Retirement Entry')
    
    def action_approve(self):
        self.state = 'approved'
        
    def action_register_payment(self):
        # We enforce feature gate
        self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.state = 'paid'
        
    def action_retire(self):
        self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.state = 'retired'
