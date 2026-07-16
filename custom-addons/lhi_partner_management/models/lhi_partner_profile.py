# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiPartnerProfile(models.Model):
    _name = 'lhi.partner.profile'
    _description = 'Partner Profile'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade')
    
    # Due Diligence & Risk
    due_diligence_status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected')
    ], string='Due Diligence Status', default='pending', tracking=True)
    
    due_diligence_date = fields.Date(string='Last Due Diligence Date', tracking=True)
    
    risk_rating = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Risk Rating', tracking=True)
    
    compliance_findings = fields.Text(string='Compliance Findings', tracking=True)
    capacity_development_actions = fields.Text(string='Capacity Development Actions', tracking=True)
    
    subaward_ids = fields.One2many('lhi.subaward', 'partner_profile_id', string='Sub-Awards')
