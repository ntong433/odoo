# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProcurementCommitment(models.Model):
    _name = 'lhi.procurement.commitment'
    _description = 'Procurement Operational Commitment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Commitment Reference', required=True, default='New', tracking=True)
    request_id = fields.Many2one('lhi.purchase.request', string='Purchase Request', required=True, ondelete='cascade', tracking=True)
    
    project_id = fields.Many2one(related='request_id.project_id', store=True)
    department_id = fields.Many2one(related='request_id.department_id', store=True)
    cost_center_id = fields.Many2one(related='request_id.cost_center_id', store=True)
    budget_line_id = fields.Many2one(related='request_id.budget_line_id', store=True)
    
    amount_reserved = fields.Monetary(string='Amount Reserved', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(related='request_id.currency_id', store=True)
    
    state = fields.Selection([
        ('reserved', 'Reserved'),
        ('released', 'Released'),
        ('consumed', 'Consumed (Converted to PO)'),
    ], string='Status', default='reserved', tracking=True)
    
    company_id = fields.Many2one(related='request_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.procurement.commitment') or 'COM-New'
        return super(LhiProcurementCommitment, self).create(vals_list)

    def action_release(self):
        self.write({'state': 'released', 'amount_reserved': 0.0})
        self.message_post(body=_("Commitment released."))
