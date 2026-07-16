# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiAsset(models.Model):
    _name = 'lhi.asset'
    _description = 'LHI Operational Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Asset Name', required=True, tracking=True)
    asset_tag = fields.Char(string='Asset Tag', required=True, copy=False, default='New')
    serial_number = fields.Char(string='Serial Number', tracking=True)
    
    category_id = fields.Many2one('lhi.asset.category', string='Category', required=True, tracking=True)
    
    # Custody & Location
    custodian_id = fields.Many2one('res.users', string='Current Custodian', tracking=True)
    location_id = fields.Many2one('lhi.location', string='Physical Location', tracking=True)
    
    # Funding & Ownership
    donor_id = fields.Many2one('res.partner', string='Donor', tracking=True)
    grant_id = fields.Char(string='Grant Reference', tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    ownership_restriction = fields.Text(string='Ownership/Disposal Restrictions')
    
    # Procurement Info
    purchase_order_id = fields.Many2one('lhi.purchase.order', string='Purchase Order', tracking=True)
    acquisition_date = fields.Date(string='Acquisition Date', tracking=True)
    warranty_expiry = fields.Date(string='Warranty Expiry', tracking=True)
    
    condition = fields.Selection([
        ('new', 'New'),
        ('good', 'Good / Operational'),
        ('fair', 'Fair / Needs Repair'),
        ('poor', 'Poor / End of Life'),
        ('broken', 'Broken / Written-off')
    ], string='Condition', default='new', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft / Received'),
        ('active', 'Active / In Use'),
        ('maintenance', 'In Maintenance'),
        ('transfer', 'In Transfer Workflow'),
        ('disposed', 'Disposed / Written-off')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    
    transfer_ids = fields.One2many('lhi.asset.transfer', 'asset_id', string='Transfer History')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_tag') or vals.get('asset_tag') == 'New':
                vals['asset_tag'] = self.env['ir.sequence'].next_by_code('lhi.asset') or 'AST-New'
        return super(LhiAsset, self).create(vals_list)

    def action_activate(self):
        self.write({'state': 'active'})

class LhiAssetCategory(models.Model):
    _name = 'lhi.asset.category'
    _description = 'LHI Asset Category'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)


class LhiAssetTransfer(models.Model):
    _name = 'lhi.asset.transfer'
    _description = 'Asset Transfer Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, default='New')
    asset_id = fields.Many2one('lhi.asset', string='Asset', required=True, ondelete='cascade', tracking=True)
    
    transfer_type = fields.Selection([
        ('handover', 'Custody Handover'),
        ('location', 'Location Move'),
        ('maintenance', 'Send to Maintenance'),
        ('write_off', 'Write-Off / Disposal'),
        ('donation', 'Donation / Handover to Partner')
    ], string='Transfer Type', required=True, tracking=True)
    
    source_custodian_id = fields.Many2one(related='asset_id.custodian_id', string='Current Custodian')
    dest_custodian_id = fields.Many2one('res.users', string='New Custodian', tracking=True)
    
    source_location_id = fields.Many2one(related='asset_id.location_id', string='Current Location')
    dest_location_id = fields.Many2one('lhi.location', string='New Location', tracking=True)
    
    justification = fields.Text(string='Justification / Notes', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one(related='asset_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.asset.transfer') or 'TRF-New'
        return super(LhiAssetTransfer, self).create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})
        self.asset_id.write({'state': 'transfer'})
        
    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_complete(self):
        if self.state != 'approved':
            raise ValidationError(_("Transfer must be approved before completion."))
            
        for rec in self:
            asset_vals = {}
            if rec.transfer_type == 'handover':
                asset_vals['custodian_id'] = rec.dest_custodian_id.id
                asset_vals['state'] = 'active'
            elif rec.transfer_type == 'location':
                asset_vals['location_id'] = rec.dest_location_id.id
                asset_vals['state'] = 'active'
            elif rec.transfer_type == 'maintenance':
                asset_vals['state'] = 'maintenance'
            elif rec.transfer_type in ('write_off', 'donation'):
                asset_vals['state'] = 'disposed'
                asset_vals['custodian_id'] = False
                
            rec.asset_id.write(asset_vals)
            rec.state = 'completed'

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.asset_id.write({'state': 'active'})

class LhiLocation(models.Model):
    _name = 'lhi.location'
    _description = 'LHI Physical Location'

    name = fields.Char(string='Location Name', required=True)
    type = fields.Selection([
        ('hq', 'Headquarters'),
        ('field', 'Field Office'),
        ('warehouse', 'Central Warehouse'),
        ('project', 'Project Site')
    ], string='Type', required=True)
