# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiWhtCertificate(models.Model):
    _name = 'lhi.wht.certificate'
    _description = 'Withholding Tax Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Certificate Number', required=True, copy=False, default='New')
    vendor_id = fields.Many2one('res.partner', string='Vendor', required=True)
    move_id = fields.Many2one('account.move', string='Related Vendor Bill')
    amount = fields.Monetary(string='WHT Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='move_id.currency_id')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('remitted', 'Remitted to FIRS/SIRS'),
        ('delivered', 'Delivered to Vendor')
    ], string='Status', default='draft', tracking=True)
    
    evidence_attachment = fields.Binary(string='Remittance Evidence')

    def action_approve(self):
        self.state = 'approved'

    def action_remit(self):
        self.state = 'remitted'
        
    def action_deliver(self):
        self.state = 'delivered'
