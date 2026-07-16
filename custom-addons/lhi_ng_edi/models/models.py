# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiNgEdiAdapter(models.Model):
    _name = 'lhi.ng.edi.adapter'
    _description = 'NRS E-Invoicing Adapter Framework'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Document ID', required=True)
    move_id = fields.Many2one('account.move', string='Invoice', required=True)
    provider = fields.Selection([
        ('nrs', 'Nigeria Revenue Service (NRS)')
    ], string='Provider', default='nrs', required=True)
    schema_version = fields.Char(string='Schema Version', default='v1.0')
    
    payload = fields.Text(string='Immutable Payload', readonly=True)
    response_data = fields.Text(string='Response/Receipt', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft / Queued'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted by Authority'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    retry_count = fields.Integer(string='Retry Count', default=0)
    idempotency_key = fields.Char(string='Idempotency Key', required=True, copy=False)
    
    def action_submit(self):
        # Only active if accounting cutover is approved, 
        # though e-invoicing might also need a separate compliance flag
        self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.state = 'sent'
        # Emulate async submission queue logic here

    def action_cancel(self):
        self.state = 'cancelled'

class AccountMove(models.Model):
    _inherit = 'account.move'

    lhi_edi_document_ids = fields.One2many('lhi.ng.edi.adapter', 'move_id', string='E-Invoicing Documents')
