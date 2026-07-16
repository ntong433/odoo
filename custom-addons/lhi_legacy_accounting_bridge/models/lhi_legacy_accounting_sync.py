# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import uuid

class LhiLegacyAccountingSync(models.Model):
    _name = 'lhi.legacy.accounting.sync'
    _description = 'Legacy Accounting Integration Sync Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Sync Reference', required=True, copy=False, default='New')
    integration_uuid = fields.Char(string='Integration UUID', required=True, copy=False, default=lambda self: str(uuid.uuid4()), readonly=True)
    
    res_model = fields.Char(string='Resource Model', required=True)
    res_id = fields.Integer(string='Resource ID', required=True)
    
    sync_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Transfer'),
        ('transferred', 'Transferred / Awaiting Processing'),
        ('accepted', 'Accepted by Accounting'),
        ('rejected', 'Rejected by Accounting')
    ], string='Sync Status', default='draft', tracking=True)
    
    # Bill & Payment Status received from Accounting
    bill_number = fields.Char(string='Bill Number', tracking=True)
    posting_status = fields.Char(string='Posting Status', tracking=True)
    payment_status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid')
    ], string='Payment Status', default='not_paid', tracking=True)
    payment_date = fields.Date(string='Payment Date', tracking=True)
    payment_reference = fields.Char(string='Payment Reference', tracking=True)
    wht_amount = fields.Monetary(string='WHT Amount', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    rejection_comments = fields.Text(string='Rejection Comments', tracking=True)
    last_sync_date = fields.Datetime(string='Last Sync Date', tracking=True)
    error_log = fields.Text(string='Error Logs')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.legacy.accounting.sync') or 'SYNC-New'
        return super(LhiLegacyAccountingSync, self).create(vals_list)

    def action_transfer(self):
        # In reality, this sends a payload to Odoo Enterprise via XML-RPC or REST API
        # using the integration_uuid as the idempotency key.
        self.write({
            'sync_status': 'transferred',
            'last_sync_date': fields.Datetime.now()
        })
        self.message_post(body=_("Procurement package transferred to Legacy Accounting."))

    def process_accounting_update(self, vals):
        # Called by a webhook or cron job polling the legacy system
        update_vals = {
            'last_sync_date': fields.Datetime.now()
        }
        
        if 'bill_number' in vals: update_vals['bill_number'] = vals['bill_number']
        if 'posting_status' in vals: update_vals['posting_status'] = vals['posting_status']
        if 'payment_status' in vals: update_vals['payment_status'] = vals['payment_status']
        if 'payment_date' in vals: update_vals['payment_date'] = vals['payment_date']
        if 'payment_reference' in vals: update_vals['payment_reference'] = vals['payment_reference']
        if 'wht_amount' in vals: update_vals['wht_amount'] = vals['wht_amount']
        if 'rejection_comments' in vals: update_vals['rejection_comments'] = vals['rejection_comments']
        
        if vals.get('rejected'):
            update_vals['sync_status'] = 'rejected'
        elif vals.get('accepted'):
            update_vals['sync_status'] = 'accepted'
            
        self.write(update_vals)
        
        # Notify source model
        source = self.env[self.res_model].browse(self.res_id)
        if source.exists() and hasattr(source, 'accounting_sync_hook'):
            source.accounting_sync_hook(self.id)
