# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiProjectReport(models.Model):
    _name = 'lhi.project.report'
    _description = 'Project Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Report Title', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    report_type = fields.Selection([
        ('narrative', 'Narrative Report'),
        ('financial', 'Financial Report'),
        ('indicator', 'Indicator Report'),
        ('procurement', 'Procurement Report'),
        ('partner', 'Partner Report'),
        ('asset', 'Asset Report'),
        ('audit', 'Audit Report'),
        ('final', 'Final Report')
    ], string='Report Type', required=True, tracking=True)
    
    owner_id = fields.Many2one('res.users', string='Report Owner', required=True, tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Reviewer', tracking=True)
    contributor_ids = fields.Many2many('res.users', string='Contributors')
    
    deadline = fields.Date(string='Internal Deadline', tracking=True)
    submission_date = fields.Date(string='Submission Date', tracking=True)
    
    version = fields.Integer(string='Version', default=1, tracking=True)
    content = fields.Html(string='Report Content')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    donor_feedback = fields.Text(string='Donor Feedback', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('review', 'Internal Review'),
        ('submitted', 'Submitted to Donor'),
        ('revised', 'Revisions Requested'),
        ('approved', 'Approved')
    ], string='Status', default='draft', tracking=True)

    def action_in_progress(self):
        self.state = 'in_progress'
        
    def action_review(self):
        self.state = 'review'
        
    def action_submit(self):
        self.state = 'submitted'
        self.submission_date = fields.Date.context_today(self)
        
    def action_request_revision(self):
        self.state = 'revised'
        self.version += 1
        
    def action_approve(self):
        self.state = 'approved'
