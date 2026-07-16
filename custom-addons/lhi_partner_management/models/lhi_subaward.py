# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiSubaward(models.Model):
    _name = 'lhi.subaward'
    _description = 'Partner Sub-Award'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Agreement Reference', required=True, tracking=True)
    partner_profile_id = fields.Many2one('lhi.partner.profile', string='Partner', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    
    total_budget = fields.Monetary(string='Total Budget', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    disbursement_ids = fields.One2many('lhi.subaward.disbursement', 'subaward_id', string='Disbursements')
    deliverable_ids = fields.One2many('lhi.subaward.deliverable', 'subaward_id', string='Deliverables')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', tracking=True)

class LhiSubawardDisbursement(models.Model):
    _name = 'lhi.subaward.disbursement'
    _description = 'Sub-Award Disbursement & Liquidation'

    subaward_id = fields.Many2one('lhi.subaward', string='Sub-Award', required=True, ondelete='cascade')
    name = fields.Char(string='Reference/Tranche', required=True)
    
    date_disbursed = fields.Date(string='Disbursement Date')
    amount_disbursed = fields.Monetary(string='Amount Disbursed', currency_field='currency_id')
    
    date_liquidated = fields.Date(string='Liquidation Date')
    amount_liquidated = fields.Monetary(string='Amount Liquidated', currency_field='currency_id')
    
    currency_id = fields.Many2one(related='subaward_id.currency_id', store=True)
    
    status = fields.Selection([
        ('pending', 'Pending Disbursement'),
        ('disbursed', 'Disbursed (Pending Liquidation)'),
        ('liquidated', 'Liquidated')
    ], string='Status', default='pending')

class LhiSubawardDeliverable(models.Model):
    _name = 'lhi.subaward.deliverable'
    _description = 'Sub-Award Deliverable'

    subaward_id = fields.Many2one('lhi.subaward', string='Sub-Award', required=True, ondelete='cascade')
    name = fields.Char(string='Deliverable Name', required=True)
    description = fields.Text(string='Description')
    due_date = fields.Date(string='Due Date')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending')
