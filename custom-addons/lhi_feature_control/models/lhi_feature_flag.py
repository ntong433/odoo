# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LhiFeatureFlag(models.Model):
    _name = 'lhi.feature.flag'
    _description = 'LHI Feature Flag'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Feature Key', required=True, index=True)
    description = fields.Text(string='Description')
    is_enabled = fields.Boolean(string='Is Enabled', default=False, tracking=True)

    _name_uniq = models.Constraint(
        'unique(name)',
        'The feature flag key must be unique!'
    )

    @api.model
    def is_flag_enabled(self, name):
        """Returns True if the feature flag exists and is enabled, otherwise False (fails closed)."""
        flag = self.sudo().search([('name', '=', name)], limit=1)
        return flag.is_enabled if flag else False

    @api.model
    def check_accounting_enabled(self):
        """Raises UserError if Accounting is disabled under feature flag."""
        if not self.env.registry.ready:
            return
        if not self.is_flag_enabled('lhi_accounting_enabled'):
            raise UserError(_("The Accounting feature is currently disabled under the LHI feature gate policy."))

    def action_enable(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only administrators can activate feature flags."))
        
        # Log audit event
        self.env['lhi.audit.log'].create_event(
            event_type='feature_flag_toggle',
            res_model=self._name,
            res_id=self.id,
            description=_("Feature flag '%s' activated by administrative request.") % self.name,
            old_value='False',
            new_value='True'
        )

        self.message_post(body=_("Feature flag '%s' activated by administrative request.") % self.name)
        self.write({'is_enabled': True})

    def action_disable(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only administrators can deactivate feature flags."))
        
        # Log audit event
        self.env['lhi.audit.log'].create_event(
            event_type='feature_flag_toggle',
            res_model=self._name,
            res_id=self.id,
            description=_("Feature flag '%s' deactivated by administrative request.") % self.name,
            old_value='True',
            new_value='False'
        )

        self.message_post(body=_("Feature flag '%s' deactivated by administrative request.") % self.name)
        self.write({'is_enabled': False})
