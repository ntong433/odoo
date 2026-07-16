# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiReportingCalendar(models.Model):
    _name = 'lhi.reporting.calendar'
    _description = 'Project Reporting Calendar'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Report Name', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    award_id = fields.Many2one(related='project_id.award_id', store=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)

    report_type = fields.Selection([
        ('financial', 'Financial Report'),
        ('narrative', 'Narrative Report'),
        ('audit', 'Audit Report'),
        ('meal', 'MEAL Report'),
        ('other', 'Other Compliance')
    ], string='Report Type', required=True)

    frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Bi-Annual'),
        ('annual', 'Annual'),
        ('final', 'Final Closeout')
    ], string='Frequency')

    due_date = fields.Date(string='Due Date', required=True, tracking=True)
    submission_date = fields.Date(string='Actual Submission Date', tracking=True)
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('draft', 'In Progress'),
        ('review', 'Under Review'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted by Donor'),
        ('late', 'Overdue')
    ], string='Status', default='pending', tracking=True, required=True)

    owner_id = fields.Many2one('res.users', string='Responsible Person', required=True, tracking=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    def action_mark_in_progress(self):
        self.status = 'draft'

    def action_submit_review(self):
        self.status = 'review'
        
    def action_mark_submitted(self):
        self.status = 'submitted'
        self.submission_date = fields.Date.context_today(self)

    @api.model
    def _cron_check_overdue_reports(self):
        today = fields.Date.context_today(self)
        overdue_reports = self.search([
            ('status', 'in', ['pending', 'draft', 'review']),
            ('due_date', '<', today)
        ])
        for report in overdue_reports:
            report.status = 'late'
            report.activity_schedule(
                'mail.mail_activity_data_warning',
                user_id=report.owner_id.id,
                summary=_('Report Overdue: %s') % report.name
            )

    @api.model
    def _cron_upcoming_deadlines(self):
        # 14 days warning
        from dateutil.relativedelta import relativedelta
        warning_date = fields.Date.context_today(self) + relativedelta(days=14)
        upcoming_reports = self.search([
            ('status', 'in', ['pending', 'draft']),
            ('due_date', '<=', warning_date),
            ('due_date', '>=', fields.Date.context_today(self))
        ])
        for report in upcoming_reports:
            report.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=report.owner_id.id,
                summary=_('Upcoming Deadline (14 days): %s') % report.name
            )
