# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiResultsFramework(models.Model):
    _name = 'lhi.results.framework'
    _description = 'Results Framework'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Framework Name', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    element_ids = fields.One2many('lhi.results.element', 'framework_id', string='Hierarchy Elements')

class LhiResultsElement(models.Model):
    _name = 'lhi.results.element'
    _description = 'Results Framework Element'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Description', required=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    sequence = fields.Integer(default=10)
    
    framework_id = fields.Many2one('lhi.results.framework', string='Framework', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='framework_id.company_id', store=True)
    
    element_type = fields.Selection([
        ('goal', 'Goal'),
        ('outcome', 'Outcome'),
        ('output', 'Output')
    ], string='Level', required=True, tracking=True)
    
    parent_id = fields.Many2one('lhi.results.element', string='Parent Element', index=True, ondelete='cascade')
    child_ids = fields.One2many('lhi.results.element', 'parent_id', string='Children')
    
    indicator_ids = fields.One2many('lhi.indicator', 'element_id', string='Indicators')
