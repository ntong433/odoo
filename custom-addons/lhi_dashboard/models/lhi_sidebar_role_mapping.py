# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.lhi_security.models.res_users import LHI_APP_SELECTION

class LhiSidebarRoleMapping(models.Model):
    _name = 'lhi.sidebar.role.mapping'
    _description = 'LHI Sidebar Role Mapping'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    app_key = fields.Selection(
        selection=LHI_APP_SELECTION,
        string="LHI Application",
        index=True,
        help="Central application entitlement used for sidebar visibility.",
    )
    group_id = fields.Many2one(
        'res.groups',
        string='Legacy Manager Group',
        help='Retained for migration history only; it no longer grants access.',
    )
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

    @api.constrains("active", "app_key")
    def _check_active_app_key(self):
        if any(mapping.active and not mapping.app_key for mapping in self):
            raise ValidationError(
                _("An active sidebar mapping must use an LHI Application entitlement.")
            )
