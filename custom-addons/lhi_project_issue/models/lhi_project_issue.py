# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiProjectIssue(models.Model):
    _name = 'lhi.project.issue'
    _description = 'Project Issue Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Issue Title', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    owner_id = fields.Many2one('res.users', string='Issue Owner', required=True, tracking=True)
    description = fields.Text(string='Description', required=True)
    
    corrective_action = fields.Text(string='Corrective Actions', tracking=True)
    due_date = fields.Date(string='Resolution Due Date', tracking=True)
    
    resolution_evidence_ids = fields.Many2many('ir.attachment', string='Resolution Evidence')
    closure_approval_id = fields.Many2one('res.users', string='Approved By (Closure)', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('resolved', 'Resolved (Pending Approval)'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True, required=True)

    def action_open(self):
        self.state = 'open'
        
    def action_resolve(self):
        self.state = 'resolved'
        
    def action_close(self):
        self.closure_approval_id = self.env.user.id
        self.state = 'closed'
