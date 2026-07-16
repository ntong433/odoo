# -*- coding: utf-8 -*-
from odoo import models

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        # Block payment posting
        if not self.env.context.get('lhi_ignore_accounting_gate'):
            self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
            
        return super(AccountPayment, self).action_post()
