# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiPurchaseRequestInherit(models.Model):
    _inherit = 'lhi.purchase.request'

    commitment_id = fields.Many2one('lhi.procurement.commitment', string='Budget Commitment', readonly=True)

    def write(self, vals):
        # Override to catch approval and cancellation from the PR
        res = super(LhiPurchaseRequestInherit, self).write(vals)
        
        for req in self:
            if 'lhi_approval_state' in vals and vals['lhi_approval_state'] == 'approved' and req.state == 'approved':
                # Create a commitment
                if not req.commitment_id:
                    commitment = self.env['lhi.procurement.commitment'].create({
                        'request_id': req.id,
                        'amount_reserved': req.total_estimated_amount,
                    })
                    req.commitment_id = commitment.id
                    
            if 'state' in vals and vals['state'] == 'cancelled':
                if req.commitment_id and req.commitment_id.state == 'reserved':
                    req.commitment_id.action_release()
                    
        return res
