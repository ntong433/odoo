# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    lhi_accounting_cutover_active = fields.Boolean(
        string='Activate LHI Production Accounting',
        config_parameter='lhi_accounting_base.is_accounting_cutover_active',
        help="Warning: Checking this box activates full financial accounting. Do not enable without executive migration approval."
    )
