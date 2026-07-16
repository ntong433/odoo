# -*- coding: utf-8 -*-
from odoo import models

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def button_validate(self):
        # Block bank reconciliation
        if not self.env.context.get('lhi_ignore_accounting_gate'):
            self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
            
        return super(AccountBankStatement, self).button_validate()
