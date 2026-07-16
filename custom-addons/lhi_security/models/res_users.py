# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    lhi_department_ids = fields.Many2many(
        'lhi.department',
        'res_users_lhi_department_rel',
        'user_id',
        'department_id',
        string='LHI Departments',
        help='Departments this user is restricted to/associated with'
    )
    lhi_project_ids = fields.Many2many(
        'lhi.project',
        'res_users_lhi_project_rel',
        'user_id',
        'project_id',
        string='LHI Projects',
        help='Projects this user is restricted to/associated with'
    )
    lhi_office_ids = fields.Many2many(
        'lhi.office',
        'res_users_lhi_office_rel',
        'user_id',
        'office_id',
        string='LHI Offices/Locations',
        help='Offices/Locations this user is restricted to/associated with'
    )
