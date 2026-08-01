# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiUnifiedInbox(models.Model):
    _name = 'lhi.unified.inbox'
    _description = 'Unified Approval Inbox'
    _order = 'create_date desc'

    name = fields.Char(string='Title', required=True)
    approver_id = fields.Many2one('res.users', string='Approver', required=True, index=True)
    
    source_system = fields.Selection([
        ('odoo', 'Odoo Core'),
        ('leave', 'External Leave System'),
        ('opensign', 'OpenSign')
    ], string='Source System', required=True)
    
    reference_model = fields.Char(string='Odoo Reference Model')
    reference_id = fields.Integer(string='Odoo Reference ID')
    
    external_reference = fields.Char(string='External ID / Deep Link ID')
    action_url = fields.Char(string='Action URL')
    
    status = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', index=True)
    
    description = fields.Text(string='Description / Summary')
    
    def action_approve_local(self):
        # Implementation for Odoo native approvals from inbox
        self.env.user.check_lhi_app_access("approvals")
        pass
        
    def action_reject_local(self):
        self.env.user.check_lhi_app_access("approvals")
        pass
