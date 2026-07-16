# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiPurchaseOrder(models.Model):
    _name = 'lhi.purchase.order'
    _description = 'LHI Purchase Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='PO Reference', required=True, default='New', tracking=True)
    sourcing_id = fields.Many2one('lhi.sourcing', string='Source Event', readonly=True)
    vendor_id = fields.Many2one('lhi.vendor', string='Vendor', required=True, tracking=True)
    
    # We bring down these fields from PR/Sourcing for standalone viewing
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    department_id = fields.Many2one('lhi.department', string='Department')
    cost_center_id = fields.Many2one('lhi.cost.center', string='Cost Center')
    budget_line_id = fields.Many2one('lhi.budget.line', string='Budget Line', tracking=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    date_order = fields.Datetime(string='Order Date', default=fields.Datetime.now, required=True, tracking=True)
    
    line_ids = fields.One2many('lhi.purchase.order.line', 'order_id', string='Order Lines')
    amount_total = fields.Monetary(string='Total Amount', compute='_compute_amount_total', store=True, currency_field='currency_id', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('locked', 'Locked / Sent'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    receipt_ids = fields.One2many('lhi.receipt', 'order_id', string='Receipts')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.purchase.order') or 'PO-New'
        return super(LhiPurchaseOrder, self).create(vals_list)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_subtotal'))

    def action_submit(self):
        # Trigger internal approval workflow if needed, or if OpenSign handles it, just set to approve
        self.write({'state': 'to_approve'})
        
    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_lock(self):
        self.write({'state': 'locked'})
        
    def action_cancel(self):
        self.write({'state': 'cancel'})

class LhiPurchaseOrderLine(models.Model):
    _name = 'lhi.purchase.order.line'
    _description = 'LHI Purchase Order Line'

    order_id = fields.Many2one('lhi.purchase.order', string='Order Reference', required=True, ondelete='cascade')
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    qty_received = fields.Float(string='Received Quantity', default=0.0, copy=False)
    price_unit = fields.Monetary(string='Unit Price', required=True, currency_field='currency_id')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True, currency_field='currency_id')
    
    currency_id = fields.Many2one(related='order_id.currency_id', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

class LhiSourcingInheritPO(models.Model):
    _inherit = 'lhi.sourcing'

    po_id = fields.Many2one('lhi.purchase.order', string='Generated PO', readonly=True)

    def action_generate_po(self):
        self.ensure_one()
        if self.state != 'awarded':
            raise ValidationError(_("Can only generate a PO from an Awarded sourcing event."))
        if self.po_id:
            raise ValidationError(_("A PO has already been generated for this sourcing event."))
            
        awarded_bid = self.bid_ids.filtered(lambda b: b.state == 'awarded')
        if not awarded_bid:
            raise ValidationError(_("No awarded bid found."))
            
        po_vals = {
            'sourcing_id': self.id,
            'vendor_id': awarded_bid[0].vendor_id.id,
            'project_id': self.request_id.project_id.id,
            'department_id': self.request_id.department_id.id,
            'cost_center_id': self.request_id.cost_center_id.id,
            'budget_line_id': self.request_id.budget_line_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'line_ids': []
        }
        
        # In a real scenario we might map specific items bid on. We'll map the original request lines
        # and set unit price from the bid (if single sum, distribute or take line details).
        # For simplicity, if bid is single amount, we create one line or prorate.
        # Here we just copy the original PR lines and trust the user to adjust to bid totals,
        # or we just create a single summary line for the total bid amount.
        
        po_vals['line_ids'].append((0, 0, {
            'name': f"Agreed delivery for Sourcing {self.name}",
            'quantity': 1,
            'price_unit': awarded_bid[0].financial_amount
        }))
        
        po = self.env['lhi.purchase.order'].create(po_vals)
        self.po_id = po.id
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'lhi.purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }
