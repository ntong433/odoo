# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    lhi_donor_currency_id = fields.Many2one('res.currency', string='Donor Reporting Currency')
    lhi_donor_exchange_rate = fields.Float(string='Donor Exchange Rate', digits=(12, 6))
    lhi_rate_source = fields.Selection([
        ('cbn', 'CBN'),
        ('donor_fixed', 'Donor Fixed'),
        ('market', 'Market Rate')
    ], string='Exchange Rate Source')
    lhi_rate_date = fields.Date(string='Rate Date')
    lhi_rate_override_reason = fields.Char(string='Override Reason')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    lhi_donor_amount = fields.Monetary(string='Donor Currency Amount', currency_field='lhi_donor_currency_id')
    lhi_donor_currency_id = fields.Many2one('res.currency', related='move_id.lhi_donor_currency_id')
