# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    lhi_department_ids = fields.Many2many(
        'lhi.department',
        'res_users_lhi_department_rel',
        'user_id',
        'department_id',
        string='LHI Departments',
        help='Departments this user is restricted to/associated with'
    )
    lhi_project_ids = fields.Many2many(
        'lhi.project',
        'res_users_lhi_project_rel',
        'user_id',
        'project_id',
        string='LHI Projects',
        help='Projects this user is restricted to/associated with'
    )
    lhi_office_ids = fields.Many2many(
        'lhi.office',
        'res_users_lhi_office_rel',
        'user_id',
        'office_id',
        string='LHI Offices/Locations',
        help='Offices/Locations this user is restricted to/associated with'
    )

    @api.model
    def _lhi_is_protected_administrator(self, user=None):
        """Returns True if the target user is the protected technical root administrator."""
        target_user = user or self.env.user
        if not target_user or not target_user.id:
            return False

        # SUPERUSER_ID (1), base.user_admin (2), or login 'admin'
        admin_ref = self.env.ref('base.user_admin', raise_if_not_found=False)
        admin_id = admin_ref.id if admin_ref else 2
        if target_user.id in (SUPERUSER_ID, admin_id) or (target_user.login and target_user.login.strip().lower() == 'admin'):
            return True

        # Check if user has LHI ERP Administrator group
        erp_admin_group = self.env.ref('lhi_security.group_lhi_erp_admin', raise_if_not_found=False)
        if erp_admin_group and erp_admin_group in target_user.all_group_ids:
            return True

        return False

    def unlink(self):
        for user in self:
            if user._lhi_is_protected_administrator(user):
                raise UserError(_("The protected administrator account cannot be deleted."))
        return super().unlink()

    def action_archive(self):
        for user in self:
            if user._lhi_is_protected_administrator(user):
                raise UserError(_("The protected administrator account cannot be archived or deactivated."))
        return super().action_archive()

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            for user in self:
                if user._lhi_is_protected_administrator(user):
                    raise UserError(_("The protected administrator account cannot be deactivated."))

        # Non-root users cannot modify protected root accounts
        if not self.env.user._lhi_is_protected_administrator():
            for user in self:
                if user._lhi_is_protected_administrator(user):
                    raise AccessError(_("Only a protected maintenance process can modify protected administrator accounts."))

        return super().write(vals)
