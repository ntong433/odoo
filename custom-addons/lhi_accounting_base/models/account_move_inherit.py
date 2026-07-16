# -*- coding: utf-8 -*-
from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # Allow internal system creations/postings IF they are purely operational
        # But generally, accounting posts are blocked until cutover.
        # We will block standard UI posting to ensure no real financial journals are committed.
        
        # We exempt operational synchronizations if needed, but the prompt strictly asks to block
        # journal posting, valuation entries, vendor bill creation.
        
        # We check the feature gate
        if not self.env.context.get('lhi_ignore_accounting_gate'):
            self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
            
        return super(AccountMove, self).action_post()
