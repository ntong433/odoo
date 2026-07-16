# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiRiskLikelihood(models.Model):
    _name = 'lhi.risk.likelihood'
    _description = 'Risk Likelihood'
    _order = 'value asc'

    name = fields.Char(string='Name', required=True)
    value = fields.Integer(string='Value (1-5)', required=True)
    description = fields.Text(string='Description')

class LhiRiskImpact(models.Model):
    _name = 'lhi.risk.impact'
    _description = 'Risk Impact'
    _order = 'value asc'

    name = fields.Char(string='Name', required=True)
    value = fields.Integer(string='Value (1-5)', required=True)
    description = fields.Text(string='Description')

class LhiRiskCategory(models.Model):
    _name = 'lhi.risk.category'
    _description = 'Risk Category'
    
    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')

class LhiProjectRisk(models.Model):
    _name = 'lhi.project.risk'
    _description = 'Project Risk Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Risk Description', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    category_id = fields.Many2one('lhi.risk.category', string='Category', tracking=True)
    owner_id = fields.Many2one('res.users', string='Risk Owner', required=True, tracking=True)
    
    # Inherent Risk
    inherent_likelihood_id = fields.Many2one('lhi.risk.likelihood', string='Inherent Likelihood', required=True, tracking=True)
    inherent_impact_id = fields.Many2one('lhi.risk.impact', string='Inherent Impact', required=True, tracking=True)
    inherent_score = fields.Integer(string='Inherent Score', compute='_compute_inherent_score', store=True)
    
    # Residual Risk
    residual_likelihood_id = fields.Many2one('lhi.risk.likelihood', string='Residual Likelihood', tracking=True)
    residual_impact_id = fields.Many2one('lhi.risk.impact', string='Residual Impact', tracking=True)
    residual_score = fields.Integer(string='Residual Score', compute='_compute_residual_score', store=True)
    
    mitigation_actions = fields.Text(string='Mitigation Actions', tracking=True)
    review_date = fields.Date(string='Next Review Date', tracking=True)
    
    escalation_level = fields.Selection([
        ('none', 'Not Escalated'),
        ('management', 'Project Management'),
        ('executive', 'Executive Board'),
        ('donor', 'Donor')
    ], string='Escalation Level', default='none', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('escalated', 'Escalated'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True, required=True)

    @api.depends('inherent_likelihood_id', 'inherent_impact_id')
    def _compute_inherent_score(self):
        for risk in self:
            if risk.inherent_likelihood_id and risk.inherent_impact_id:
                risk.inherent_score = risk.inherent_likelihood_id.value * risk.inherent_impact_id.value
            else:
                risk.inherent_score = 0

    @api.depends('residual_likelihood_id', 'residual_impact_id')
    def _compute_residual_score(self):
        for risk in self:
            if risk.residual_likelihood_id and risk.residual_impact_id:
                risk.residual_score = risk.residual_likelihood_id.value * risk.residual_impact_id.value
            else:
                risk.residual_score = 0
                
    def action_activate(self):
        self.state = 'active'
        
    def action_escalate(self):
        self.state = 'escalated'
        
    def action_close(self):
        self.state = 'closed'
