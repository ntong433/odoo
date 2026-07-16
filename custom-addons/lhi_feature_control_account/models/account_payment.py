# -*- coding: utf-8 -*-
from odoo import models, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model_create_multi
    def create(self, vals_list):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountPayment, self).create(vals_list)

    def write(self, vals):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountPayment, self).write(vals)

    def unlink(self):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountPayment, self).unlink()

    def action_post(self):
        self.env['lhi.feature.flag'].check_accounting_enabled()
        return super(AccountPayment, self).action_post()
