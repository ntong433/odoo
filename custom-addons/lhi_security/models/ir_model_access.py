# -*- coding: utf-8 -*-
from odoo import models, api


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        """Bypass model ACL restrictions for the protected administrator."""
        if self.env.user._lhi_is_protected_administrator():
            return True
        return super().check(model, mode=mode, raise_exception=raise_exception)
