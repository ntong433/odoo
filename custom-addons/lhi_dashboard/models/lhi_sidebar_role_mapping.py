# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiSidebarRoleMapping(models.Model):
    _name = 'lhi.sidebar.role.mapping'
    _description = 'LHI Sidebar Role Mapping'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    group_id = fields.Many2one('res.groups', string='Manager Group', required=True, 
                               help='The manager or director group that triggers this mapping.')
    menu_id = fields.Many2one('ir.ui.menu', string='Target Menu', required=True,
                              help='The root menu item to grant access to.')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    include_for_manager = fields.Boolean(string='Include for Manager', default=True,
                                         help='If checked, users with the Manager Group will see this menu.')
    include_for_director = fields.Boolean(string='Include for Director', default=True,
                                          help='If checked, this mapping applies for Director-level portfolio resolution.')
    company_ids = fields.Many2many('res.company', string='Companies')
    notes = fields.Text(string='Notes')
