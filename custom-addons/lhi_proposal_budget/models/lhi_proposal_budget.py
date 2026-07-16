# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProposalBudget(models.Model):
    _name = 'lhi.proposal.budget'
    _description = 'Proposal Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Budget Title', required=True, tracking=True)
    workspace_id = fields.Many2one('lhi.proposal.workspace', string='Proposal Workspace', required=True, ondelete='cascade', tracking=True)
    company_id = fields.Many2one(related='workspace_id.company_id', store=True)
    
    currency_id = fields.Many2one('res.currency', string='Main Currency', default=lambda self: self.env.company.currency_id, required=True, tracking=True)
    exchange_rate_date = fields.Date(string='Exchange Rate Date', default=fields.Date.context_today)
    
    line_ids = fields.One2many('lhi.proposal.budget.line', 'budget_id', string='Budget Lines')

    # Totals
    total_donor_contribution = fields.Monetary(string='Total Donor Contribution', compute='_compute_totals', store=True, currency_field='currency_id')
    total_lhi_contribution = fields.Monetary(string='Total LHI Contribution', compute='_compute_totals', store=True, currency_field='currency_id')
    total_partner_contribution = fields.Monetary(string='Total Partner Contribution', compute='_compute_totals', store=True, currency_field='currency_id')
    total_indirect_costs = fields.Monetary(string='Total Indirect Costs', compute='_compute_totals', store=True, currency_field='currency_id')
    total_amount = fields.Monetary(string='Total Budget', compute='_compute_totals', store=True, currency_field='currency_id')

    narrative = fields.Html(string='Budget Narrative', tracking=True)
    
    @api.depends('line_ids.total_base_currency', 'line_ids.donor_contribution_base', 
                 'line_ids.lhi_contribution_base', 'line_ids.partner_contribution_base', 
                 'line_ids.indirect_costs_base')
    def _compute_totals(self):
        for record in self:
            record.total_donor_contribution = sum(record.line_ids.mapped('donor_contribution_base'))
            record.total_lhi_contribution = sum(record.line_ids.mapped('lhi_contribution_base'))
            record.total_partner_contribution = sum(record.line_ids.mapped('partner_contribution_base'))
            record.total_indirect_costs = sum(record.line_ids.mapped('indirect_costs_base'))
            record.total_amount = sum(record.line_ids.mapped('total_base_currency'))

    @api.constrains('total_donor_contribution', 'workspace_id')
    def _check_funding_ceiling(self):
        for record in self:
            ceiling = record.workspace_id.opportunity_id.funding_ceiling
            if ceiling > 0 and record.total_donor_contribution > ceiling:
                raise ValidationError(_("The total donor contribution (%s) exceeds the opportunity funding ceiling (%s).") % 
                                      (record.total_donor_contribution, ceiling))


class LhiProposalBudgetLine(models.Model):
    _name = 'lhi.proposal.budget.line'
    _description = 'Proposal Budget Line'

    budget_id = fields.Many2one('lhi.proposal.budget', string='Budget', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='budget_id.company_id', store=True)
    
    # Categories
    donor_category = fields.Char(string='Donor Category', required=True)
    lhi_category = fields.Char(string='LHI Category', required=True)
    
    # Coding
    output = fields.Char(string='Output')
    activity = fields.Char(string='Activity')
    location_id = fields.Many2one('lhi.office', string='Location', required=True)
    department_id = fields.Many2one('lhi.department', string='Department', required=True)
    cost_center_id = fields.Many2one('lhi.cost.center', string='Cost Centre', required=True)
    
    # Calculation
    unit = fields.Char(string='Unit', required=True)
    unit_cost = fields.Float(string='Unit Cost', required=True, default=0.0)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    frequency = fields.Float(string='Frequency', required=True, default=1.0)
    duration = fields.Float(string='Duration', required=True, default=1.0)
    
    # Currency
    currency_id = fields.Many2one('res.currency', string='Line Currency', required=True)
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0, help="Exchange rate to main budget currency")
    
    # Distribution
    donor_percentage = fields.Float(string='Donor %', default=100.0)
    lhi_percentage = fields.Float(string='LHI %', default=0.0)
    partner_percentage = fields.Float(string='Partner %', default=0.0)
    
    # Indirect
    indirect_cost_rate = fields.Float(string='Indirect Rate (%)', default=0.0)
    
    # Justification
    justification = fields.Text(string='Justification')

    # Computed fields (Line currency)
    line_total = fields.Float(string='Line Total', compute='_compute_line_totals', store=True)
    
    # Computed fields (Base budget currency)
    total_base_currency = fields.Float(string='Total (Base)', compute='_compute_base_totals', store=True)
    donor_contribution_base = fields.Float(string='Donor Contrib (Base)', compute='_compute_base_totals', store=True)
    lhi_contribution_base = fields.Float(string='LHI Contrib (Base)', compute='_compute_base_totals', store=True)
    partner_contribution_base = fields.Float(string='Partner Contrib (Base)', compute='_compute_base_totals', store=True)
    indirect_costs_base = fields.Float(string='Indirect Costs (Base)', compute='_compute_base_totals', store=True)

    @api.depends('unit_cost', 'quantity', 'frequency', 'duration')
    def _compute_line_totals(self):
        for record in self:
            record.line_total = record.unit_cost * record.quantity * record.frequency * record.duration
            
    @api.depends('line_total', 'exchange_rate', 'donor_percentage', 'lhi_percentage', 'partner_percentage', 'indirect_cost_rate')
    def _compute_base_totals(self):
        for record in self:
            base = record.line_total * record.exchange_rate if record.exchange_rate else record.line_total
            record.total_base_currency = base
            record.donor_contribution_base = base * (record.donor_percentage / 100.0)
            record.lhi_contribution_base = base * (record.lhi_percentage / 100.0)
            record.partner_contribution_base = base * (record.partner_percentage / 100.0)
            record.indirect_costs_base = base * (record.indirect_cost_rate / 100.0)

    @api.constrains('donor_percentage', 'lhi_percentage', 'partner_percentage')
    def _check_percentages(self):
        for record in self:
            total = record.donor_percentage + record.lhi_percentage + record.partner_percentage
            if round(total, 2) != 100.0:
                raise ValidationError(_("The sum of Donor, LHI, and Partner percentages must equal 100%%. Current sum: %s%% on line '%s'") % (total, record.donor_category))

    @api.constrains('donor_category', 'lhi_category', 'location_id', 'department_id', 'cost_center_id')
    def _check_duplicate_lines(self):
        for record in self:
            duplicates = self.search([
                ('budget_id', '=', record.budget_id.id),
                ('donor_category', '=', record.donor_category),
                ('lhi_category', '=', record.lhi_category),
                ('location_id', '=', record.location_id.id),
                ('department_id', '=', record.department_id.id),
                ('cost_center_id', '=', record.cost_center_id.id),
                ('id', '!=', record.id)
            ])
            if duplicates:
                raise ValidationError(_("A duplicate budget line with the same categories, location, department, and cost centre already exists."))
