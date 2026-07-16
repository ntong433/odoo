# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiReceipt(models.Model):
    _name = 'lhi.receipt'
    _description = 'LHI Goods Receipt & Service Acceptance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Receipt Reference', required=True, default='New', tracking=True)
    order_id = fields.Many2one('lhi.purchase.order', string='Purchase Order', required=True, ondelete='cascade', tracking=True)
    vendor_id = fields.Many2one(related='order_id.vendor_id', store=True)
    
    receipt_type = fields.Selection([
        ('goods', 'Goods Receipt'),
        ('service', 'Service Acceptance')
    ], string='Receipt Type', required=True, tracking=True)
    
    date_done = fields.Datetime(string='Date Done', default=fields.Datetime.now, tracking=True)
    
    line_ids = fields.One2many('lhi.receipt.line', 'receipt_id', string='Receipt Lines')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one(related='order_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.receipt') or 'REC-New'
        return super(LhiReceipt, self).create(vals_list)

    def action_validate(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("You must provide at least one receipt line."))
            for line in rec.line_ids:
                if line.qty_received > line.order_line_id.quantity - line.order_line_id.qty_received:
                    raise ValidationError(_("Cannot receive more than ordered for %s") % line.order_line_id.name)
                # Update PO line received qty
                line.order_line_id.qty_received += line.qty_received
            rec.state = 'done'


class LhiReceiptLine(models.Model):
    _name = 'lhi.receipt.line'
    _description = 'Receipt Line'

    receipt_id = fields.Many2one('lhi.receipt', string='Receipt', required=True, ondelete='cascade')
    order_line_id = fields.Many2one('lhi.purchase.order.line', string='Order Line', required=True)
    name = fields.Char(related='order_line_id.name', string='Description')
    qty_ordered = fields.Float(related='order_line_id.quantity', string='Ordered Quantity')
    qty_received = fields.Float(string='Received Quantity', required=True)
