# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProjectAmendment(models.Model):
    _name = 'lhi.project.amendment'
    _description = 'Project Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Amendment Title', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    amendment_type = fields.Selection([
        ('no_cost', 'No-Cost Extension'),
        ('cost', 'Cost Extension'),
        ('budget', 'Budget Revision'),
        ('geographic', 'Geographic Change'),
        ('activity', 'Activity Change'),
        ('target', 'Target Revision'),
        ('staffing', 'Staffing Change'),
        ('other', 'Other')
    ], string='Amendment Type', required=True, tracking=True)
    
    justification = fields.Text(string='Justification', required=True)
    
    original_value = fields.Text(string='Original Value/State')
    proposed_value = fields.Text(string='Proposed Value/State')
    
    amended_document_ids = fields.Many2many('ir.attachment', string='Amended Documents')
    
    # Dates
    donor_submission_date = fields.Date(string='Donor Submission Date', tracking=True)
    donor_response_date = fields.Date(string='Donor Response Date', tracking=True)
    effective_date = fields.Date(string='Effective Date', tracking=True, required=True)
    
    # Approvals
    internal_approval_id = fields.Many2one('res.users', string='Internal Approver', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('internal_review', 'Internal Review'),
        ('submitted', 'Submitted to Donor'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True, required=True)

    def action_submit_internal(self):
        self.state = 'internal_review'
        
    def action_approve_internal(self):
        self.internal_approval_id = self.env.user.id
        self.state = 'submitted'
        
    def action_donor_approve(self):
        self.state = 'approved'
        self.donor_response_date = fields.Date.context_today(self)
        
    def action_reject(self):
        self.state = 'rejected'
        self.donor_response_date = fields.Date.context_today(self)
        
    def action_apply(self):
        for record in self:
            if record.state != 'approved':
                raise ValidationError(_("Only approved amendments can be applied."))
            if record.effective_date > fields.Date.context_today(self):
                raise ValidationError(_("Cannot apply amendment before its effective date."))
            record.state = 'applied'

    @api.model
    def _cron_apply_amendments(self):
        today = fields.Date.context_today(self)
        pending_amendments = self.search([
            ('state', '=', 'approved'),
            ('effective_date', '<=', today)
        ])
        for am in pending_amendments:
            am.action_apply()
            am.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=am.create_uid.id,
                summary=_('Amendment Applied: Please update relevant records manually if necessary.')
            )
