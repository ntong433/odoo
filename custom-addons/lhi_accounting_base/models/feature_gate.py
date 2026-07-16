# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError

class LhiAccountingFeatureGate(models.AbstractModel):
    _name = 'lhi.accounting.feature.gate'
    _description = 'Accounting Feature Gate Validation'
    
    @api.model
    def check_accounting_enabled(self):
        """
        Server-side validation to strictly prevent financial operations
        if the formal LHI Accounting cutover has not been approved and activated.
        """
        is_enabled = self.env['ir.config_parameter'].sudo().get_param('lhi_accounting_base.is_accounting_cutover_active', 'False')
        if is_enabled != 'True':
            raise UserError(
                "LHI Accounting Operations are currently disabled pending formal migration cutover. "
                "Financial postings, payments, and reconciliations are restricted."
            )
        return True
