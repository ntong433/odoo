# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiPurchaseOrderAccountingInherit(models.Model):
    _inherit = 'lhi.purchase.order'

    accounting_sync_id = fields.Many2one('lhi.legacy.accounting.sync', string='Accounting Sync Record', readonly=True)
    accounting_status = fields.Selection([
        ('none', 'Not Sent'),
        ('pending', 'Pending Transfer'),
        ('transferred', 'Sent to Accounting'),
        ('accepted', 'Accepted (Bill Created)'),
        ('rejected', 'Rejected by Accounting')
    ], string='Accounting Status', default='none', tracking=True)
    
    # Mirror fields from sync record for easy viewing on PO
    payment_status = fields.Selection(related='accounting_sync_id.payment_status')
    payment_date = fields.Date(related='accounting_sync_id.payment_date')
    payment_reference = fields.Char(related='accounting_sync_id.payment_reference')
    bill_number = fields.Char(related='accounting_sync_id.bill_number')

    def action_send_to_accounting(self):
        for po in self:
            if po.state not in ('locked', 'done'):
                raise ValidationError(_("PO must be locked/signed or done before sending to accounting."))
            
            # Create Sync Record
            sync_rec = self.env['lhi.legacy.accounting.sync'].create({
                'res_model': self._name,
                'res_id': po.id,
            })
            
            # Send it
            sync_rec.action_transfer()
            
            po.accounting_sync_id = sync_rec.id
            po.accounting_status = 'transferred'

    def accounting_sync_hook(self, sync_id):
        if self.accounting_sync_id.id == sync_id:
            self.accounting_status = self.accounting_sync_id.sync_status
            if self.accounting_status == 'accepted':
                self.message_post(body=_("Procurement package accepted by Legacy Accounting. Bill Number: %s") % self.bill_number)
            elif self.accounting_status == 'rejected':
                self.message_post(body=_("Procurement package REJECTED by Legacy Accounting. Reason: %s") % self.accounting_sync_id.rejection_comments)
