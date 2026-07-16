# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiMealData(models.Model):
    _name = 'lhi.meal.data'
    _description = 'MEAL Data Collection Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_reported desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    indicator_id = fields.Many2one('lhi.indicator', string='Indicator', required=True, tracking=True)
    project_id = fields.Many2one(related='indicator_id.project_id', store=True)
    company_id = fields.Many2one(related='indicator_id.company_id', store=True)
    
    activity_id = fields.Many2one('lhi.workplan.activity', string='Related Activity')
    location_id = fields.Many2one('lhi.office', string='Location')
    
    date_reported = fields.Date(string='Reporting Date', default=fields.Date.context_today, required=True, tracking=True)
    reporting_period = fields.Char(string='Reporting Period (e.g. Q1 2030)')
    
    achieved_value = fields.Float(string='Achieved Value', required=True, tracking=True)
    unit = fields.Char(related='indicator_id.unit')
    
    # "Apply stronger security to beneficiary-level or sensitive programme information."
    is_sensitive = fields.Boolean(string='Contains Sensitive/Beneficiary Data', tracking=True)
    
    narrative = fields.Text(string='Narrative / Explanation')
    
    evidence_ids = fields.One2many('lhi.meal.evidence', 'meal_data_id', string='Means of Verification (Evidence)')
    
    reporter_id = fields.Many2one('res.users', string='Reporter', default=lambda self: self.env.user, tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Reviewer', tracking=True)
    
    correction_feedback = fields.Text(string='Correction Feedback', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Verification'),
        ('approved', 'Verified & Approved'),
        ('rejected', 'Rejected / Needs Correction')
    ], string='Status', default='draft', tracking=True, required=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.meal.data') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        if not self.evidence_ids and not self.narrative:
            raise ValidationError(_("You must provide either a narrative or evidence attachments before submitting."))
        self.state = 'submitted'
        
    def action_approve(self):
        self.ensure_one()
        self.state = 'approved'
        self.reviewer_id = self.env.user.id
        
    def action_reject(self):
        self.ensure_one()
        if not self.correction_feedback:
            raise ValidationError(_("Please provide correction feedback before rejecting."))
        self.state = 'rejected'
        self.reviewer_id = self.env.user.id
        
    @api.model
    def _cron_check_missing_evidence(self):
        records = self.search([
            ('state', 'in', ['draft', 'submitted']),
            ('evidence_ids', '=', False)
        ])
        for record in records:
            record.activity_schedule(
                'mail.mail_activity_data_warning',
                user_id=record.reporter_id.id,
                summary=_('Missing Evidence: %s') % record.name
            )
