# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiIndicator(models.Model):
    _name = 'lhi.indicator'
    _description = 'Programme Indicator'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Indicator Title', required=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    sequence = fields.Integer(default=10)
    
    element_id = fields.Many2one('lhi.results.element', string='Results Element', required=True, ondelete='cascade')
    framework_id = fields.Many2one(related='element_id.framework_id', store=True)
    company_id = fields.Many2one(related='element_id.company_id', store=True)
    project_id = fields.Many2one(related='framework_id.project_id', store=True)
    
    # "Create the hierarchy Goal -> Outcome -> Output -> Indicator -> Activity."
    # Allowing multiple activities to contribute to an indicator, or linking an indicator to a specific activity.
    # ``activity_ids`` is reserved by mail.activity.mixin for chatter
    # activities. Keep the business relationship under an explicit name.
    workplan_activity_ids = fields.Many2many(
        'lhi.workplan.activity',
        string='Linked Workplan Activities',
    )
    
    definition = fields.Text(string='Definition / Formula')
    baseline = fields.Float(string='Baseline Value', default=0.0)
    target = fields.Float(string='Target Value', required=True)
    unit = fields.Char(string='Unit of Measure', required=True)
    
    is_disaggregated = fields.Boolean(string='Requires Disaggregation')
    disaggregation_ids = fields.One2many('lhi.indicator.disaggregation', 'indicator_id', string='Disaggregation Categories')
    
    frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
        ('endline', 'Endline Only')
    ], string='Reporting Frequency', required=True)
    
    data_source = fields.Char(string='Data Source')
    means_of_verification = fields.Text(string='Means of Verification')
    
    responsible_id = fields.Many2one('res.users', string='Responsible Officer', tracking=True)
    
    # Dashboards/aggregates
    achieved_total = fields.Float(string='Total Achieved', compute='_compute_achieved_total', store=True)
    progress_percentage = fields.Float(string='Progress (%)', compute='_compute_achieved_total', store=True)
    
    @api.depends('target')
    def _compute_achieved_total(self):
        for record in self:
            # The MEAL module extends this computation once installed. Keeping
            # the base implementation independent avoids a circular model
            # dependency between Results Framework and MEAL.
            record.achieved_total = 0.0
            record.progress_percentage = 0.0

class LhiIndicatorDisaggregation(models.Model):
    _name = 'lhi.indicator.disaggregation'
    _description = 'Indicator Disaggregation Category'

    name = fields.Char(string='Category (e.g., Female, Age 18-35)', required=True)
    indicator_id = fields.Many2one('lhi.indicator', string='Indicator', required=True, ondelete='cascade')
