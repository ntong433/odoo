# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiFundingOpportunity(models.Model):
    _name = 'lhi.funding.opportunity'
    _description = 'Funding Opportunity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_deadline desc, id desc'

    name = fields.Char(string='Opportunity Title', required=True, tracking=True)
    reference = fields.Char(string='Opportunity Reference', tracking=True)
    donor_id = fields.Many2one('lhi.donor', string='Donor', required=True, tracking=True)
    
    stage_id = fields.Many2one('lhi.funding.stage', string='Stage', tracking=True, 
                               group_expand='_read_group_stage_ids',
                               default=lambda self: self._default_stage_id())
                               
    user_id = fields.Many2one('res.users', string='Owner', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Financial & Scope
    funding_ceiling = fields.Monetary(string='Funding Ceiling', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    co_financing_required = fields.Boolean(string='Co-financing Required')
    co_financing_amount = fields.Monetary(string='Co-financing Amount', currency_field='currency_id')
    duration_months = fields.Integer(string='Duration (Months)')
    
    # Categorization
    sector_id = fields.Many2one('lhi.sector', string='Primary Sector')
    programme_id = fields.Many2one('lhi.programme', string='Programme')
    geography_ids = fields.Many2many('lhi.office', string='Target Geography')
    
    # Timeline
    submission_deadline = fields.Date(string='Submission Deadline', required=True, tracking=True)
    
    # Requirements
    eligibility_notes = fields.Text(string='Eligibility Checklist')
    consortium_requirements = fields.Text(string='Consortium/Partnership Requirements')
    source_documents = fields.Html(string='Source Documents / Links')
    
    # Go / No-Go Assessment Scoring (1-10 scale)
    score_strategic_fit = fields.Integer(string='Strategic Fit', default=0)
    score_technical_capacity = fields.Integer(string='Technical Capacity', default=0)
    score_operational_presence = fields.Integer(string='Operational Presence', default=0)
    score_staffing = fields.Integer(string='Staffing Capability', default=0)
    score_compliance = fields.Integer(string='Compliance & Risk', default=0)
    score_partnerships = fields.Integer(string='Partnerships', default=0)
    score_security = fields.Integer(string='Security', default=0)
    score_financial_exposure = fields.Integer(string='Financial Exposure', default=0)
    score_timeline = fields.Integer(string='Timeline Feasibility', default=0)
    
    total_score = fields.Integer(string='Total Score', compute='_compute_total_score', store=True)
    probability = fields.Float(string='Win Probability (%)', tracking=True)
    
    approval_request_id = fields.Many2one('lhi.approval.request', string='Go/No-Go Approval', readonly=True, copy=False)
    
    @api.model
    def _default_stage_id(self):
        stage = self.env['lhi.funding.stage'].search([], order='sequence', limit=1)
        return stage.id if stage else False

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['lhi.funding.stage'].search([])

    @api.depends('score_strategic_fit', 'score_technical_capacity', 'score_operational_presence', 
                 'score_staffing', 'score_compliance', 'score_partnerships', 'score_security', 
                 'score_financial_exposure', 'score_timeline')
    def _compute_total_score(self):
        for record in self:
            record.total_score = sum([
                record.score_strategic_fit, record.score_technical_capacity, 
                record.score_operational_presence, record.score_staffing, 
                record.score_compliance, record.score_partnerships, 
                record.score_security, record.score_financial_exposure, 
                record.score_timeline
            ])
            
    def action_request_approval(self):
        self.ensure_one()
        if self.approval_request_id and self.approval_request_id.state not in ['rejected', 'cancelled']:
            raise ValidationError(_("An approval request is already pending or approved."))
            
        # Create an approval request for Go/No-Go
        matrix = self.env['lhi.approval.matrix'].search([
            ('model_name', '=', 'lhi.funding.opportunity'),
            ('active', '=', True)
        ], limit=1)
        
        if not matrix:
            raise ValidationError(_("No active approval matrix found for Funding Opportunities. Please configure one."))
            
        approval = self.env['lhi.approval.request'].create({
            'matrix_id': matrix.id,
            'res_model': 'lhi.funding.opportunity',
            'res_id': self.id,
            'reference': f"Go/No-Go Decision: {self.name}",
            'requester_id': self.env.user.id,
        })
        
        approval.action_submit()
        self.approval_request_id = approval.id
        
        # Log note
        self.message_post(body=_("Go/No-Go Approval Request %s submitted.") % approval.name)
        
    def _check_overdue_deadlines(self):
        """ Cron job to check for imminent deadlines and alert owners """
        today = fields.Date.context_today(self)
        warning_date = fields.Date.add(today, days=7)
        
        opportunities = self.search([
            ('submission_deadline', '<=', warning_date),
            ('stage_id.is_won', '=', False),
            ('stage_id.is_lost', '=', False)
        ])
        
        for opp in opportunities:
            opp.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=opp.submission_deadline,
                user_id=opp.user_id.id,
                summary=_('Upcoming Submission Deadline: %s') % opp.name,
                note=_('The submission deadline for this opportunity is approaching.')
            )
