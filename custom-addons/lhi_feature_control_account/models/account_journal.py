# -*- coding: utf-8 -*-
from odoo import models, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model_create_multi
    def create(self, vals_list):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountJournal, self).create(vals_list)

    def write(self, vals):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountJournal, self).write(vals)

    def unlink(self):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountJournal, self).unlink()
