# -*- coding: utf-8 -*-
from odoo import models, api


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _get_rules(self, model_name, mode='read'):
        """Return no record rules for protected administrator, granting unrestricted record access."""
        if self.env.user._lhi_is_protected_administrator():
            return self.browse(())
        return super()._get_rules(model_name, mode=mode)
