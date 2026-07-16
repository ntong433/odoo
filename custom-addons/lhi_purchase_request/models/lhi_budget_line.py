# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiBudgetLine(models.Model):
    _name = 'lhi.budget.line'
    _description = 'Budget Line'
    _inherit = ['mail.thread']

    name = fields.Char(string='Budget Line Code', required=True, tracking=True)
    description = fields.Char(string='Description', tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    cost_center_id = fields.Many2one('lhi.cost.center', string='Cost Centre', tracking=True)
    active = fields.Boolean(default=True)
    
    total_budget = fields.Monetary(string='Total Budget', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
