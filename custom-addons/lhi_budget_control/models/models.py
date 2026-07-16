# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LhiBudget(models.Model):
    _name = 'lhi.budget'
    _description = 'LHI Budget Control'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Budget Reference', required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (Grant)', required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('revised', 'Revised'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many('lhi.budget.line', 'budget_id', string='Budget Lines')
    tolerance_percentage = fields.Float(string='Tolerance (%)', default=0.0)

    def action_activate(self):
        self.state = 'active'
        
    def action_revise(self):
        self.state = 'revised'

class LhiBudgetLine(models.Model):
    _name = 'lhi.budget.line'
    _description = 'LHI Budget Line'

    budget_id = fields.Many2one('lhi.budget', string='Budget', required=True, ondelete='cascade')
    general_account_id = fields.Many2one('account.account', string='GL Account', required=True)
    planned_amount = fields.Monetary(string='Planned Amount', currency_field='currency_id')
    commitment_amount = fields.Monetary(string='Commitments', default=0.0, currency_field='currency_id')
    actual_amount = fields.Monetary(string='Actuals', default=0.0, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='budget_id.analytic_account_id.company_id.currency_id')
    
    @api.depends('planned_amount', 'commitment_amount', 'actual_amount')
    def _compute_available(self):
        for line in self:
            line.available_amount = line.planned_amount - line.commitment_amount - line.actual_amount

    available_amount = fields.Monetary(string='Available', compute='_compute_available', currency_field='currency_id')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.analytic_distribution and line.account_id:
                # Check budget tolerance if applicable
                pass # Logic to enforce budget would go here, checking lhi_accounting_feature_gate
        return lines
