# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiFundingStage(models.Model):
    _name = 'lhi.funding.stage'
    _description = 'Funding Opportunity Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(default=10)
    is_won = fields.Boolean(string='Is Won Stage?', help='Opportunities in this stage are considered won.')
    is_lost = fields.Boolean(string='Is Lost Stage?', help='Opportunities in this stage are considered lost.')
    fold = fields.Boolean(string='Folded in Pipeline', help='Fold this stage in the kanban view.')
    description = fields.Text(string='Description')
