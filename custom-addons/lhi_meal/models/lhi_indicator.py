# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LhiIndicator(models.Model):
    _inherit = 'lhi.indicator'

    meal_data_ids = fields.One2many(
        'lhi.meal.data',
        'indicator_id',
        string='MEAL Data',
    )

    @api.depends('meal_data_ids.achieved_value', 'meal_data_ids.state', 'target')
    def _compute_achieved_total(self):
        for record in self:
            approved_data = record.meal_data_ids.filtered(
                lambda data: data.state == 'approved'
            )
            total = sum(approved_data.mapped('achieved_value'))
            record.achieved_total = total
            record.progress_percentage = (
                (total / record.target) * 100 if record.target else 0.0
            )
