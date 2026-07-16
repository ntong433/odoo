# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    lhi_entra_object_id = fields.Char(string='Microsoft Entra Object ID', index=True, copy=False, tracking=True, 
                                      help="Used to map identity to external systems like Leave Management")
