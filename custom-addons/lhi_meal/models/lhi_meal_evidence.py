# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiMealEvidence(models.Model):
    _name = 'lhi.meal.evidence'
    _description = 'MEAL Evidence Library Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True)
    meal_data_id = fields.Many2one('lhi.meal.data', string='MEAL Record', ondelete='cascade')
    company_id = fields.Many2one(related='meal_data_id.company_id', store=True)
    
    evidence_type = fields.Selection([
        ('attendance', 'Attendance Sheet'),
        ('photo', 'Photo/Video'),
        ('report', 'Assessment Report'),
        ('survey', 'Survey Data'),
        ('other', 'Other')
    ], string='Evidence Type', required=True)
    
    is_sensitive = fields.Boolean(related='meal_data_id.is_sensitive', store=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Files', required=True)
    description = fields.Text(string='Description / Notes')
