# -*- coding: utf-8 -*-
import base64
import hashlib

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiPurchaseOrderSignatureInherit(models.Model):
    _inherit = 'lhi.purchase.order'

    opensign_request_id = fields.Many2one('lhi.opensign.request', string='OpenSign Request', readonly=True)
    signature_status = fields.Selection([
        ('none', 'Not Sent'),
        ('sent', 'Sent for Signature'),
        ('signed', 'Signed'),
        ('cancelled', 'Signature Cancelled')
    ], string='Signature Status', default='none', tracking=True)
    
    is_locked = fields.Boolean(string='Is Locked', compute='_compute_is_locked', store=True)

    @api.depends('signature_status', 'state')
    def _compute_is_locked(self):
        for po in self:
            po.is_locked = (po.signature_status in ('sent', 'signed') or po.state in ('locked', 'done', 'cancel'))

    def action_send_for_signature(self):
        for po in self:
            if po.state != 'approved':
                raise ValidationError(_("PO must be approved before sending for signature."))
            if po.signature_status in ('sent', 'signed'):
                raise ValidationError(_("Document is already sent or signed."))
                
            pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
                'lhi_signature_bridge.action_report_lhi_purchase_order',
                res_ids=[po.id],
            )
            # The bridge is a protected technical model. Elevate only the
            # deterministic request creation after the purchase-order access
            # checks above; normal users never receive direct request access.
            req = self.env['lhi.opensign.request'].sudo().create({
                'res_model': self._name,
                'res_id': po.id,
                'company_id': po.company_id.id,
                'source_pdf': base64.b64encode(pdf_content),
                'source_pdf_hash': hashlib.sha256(pdf_content).hexdigest(),
                'signatories': '{"signatories": [{"email": "vendor@example.com", "role": "Vendor"}, {"email": "director@lhi.org", "role": "Director"}]}',
            })
            req.sudo().action_send()
            po.opensign_request_id = req.id
            if req.status != 'sent':
                po.message_post(
                    body=_(
                        "Signature dispatch is pending because the generated "
                        "purchase-order PDF is not confirmed in SharePoint."
                    )
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('SharePoint storage pending'),
                        'message': req.error_message,
                        'type': 'warning',
                        'sticky': True,
                    },
                }
            po.signature_status = 'sent'

    def opensign_completed_hook(self, request_id):
        if self.opensign_request_id.id == request_id:
            self.signature_status = 'signed'
            # Auto-lock after signature
            self.action_lock()
            self.message_post(body=_("Purchase Order has been fully signed via OpenSign and is now Locked."))

    def write(self, vals):
        # Prevent changes to commercial/coding fields if locked
        restricted_fields = ['vendor_id', 'amount_total', 'project_id', 'department_id', 'cost_center_id', 'budget_line_id', 'line_ids']
        for po in self:
            if po.is_locked:
                for field in restricted_fields:
                    if field in vals:
                        raise ValidationError(_("Cannot modify commercial or coding fields (%s) while the document is locked or signed. You must cancel the signature process to make material changes.") % field)
        return super(LhiPurchaseOrderSignatureInherit, self).write(vals)

    def action_cancel_signature(self):
        for po in self:
            if po.opensign_request_id and po.signature_status != 'signed':
                po.opensign_request_id.sudo().action_cancel()
            po.signature_status = 'cancelled'
            po.message_post(body=_("Signature process was cancelled. Commercial fields are unlocked if PO state permits."))
