# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LhiBudgetLine(models.Model):
    _name = 'lhi.budget.line'
    _description = 'LHI Operational Budget Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Budget Line Code', required=False, tracking=True)
    description = fields.Char(string='Description', tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    cost_center_id = fields.Many2one('lhi.cost.center', string='Cost Centre', tracking=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)

    total_budget = fields.Monetary(
        string='Operational Budget',
        currency_field='currency_id',
        tracking=True,
        help='Operational planning value. This field does not create accounting entries.',
    )
