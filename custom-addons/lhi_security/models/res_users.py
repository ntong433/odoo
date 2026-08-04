# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError


LHI_APP_LABELS = {
    "operations": "Operations",
    "hub": "HUB",
    "assets": "Asset Register",
    "procurement": "Procurement",
    "inventory": "Inventory",
    "fleet": "Fleet",
    "programs_grants": "Programs & Grants",
    "approvals": "Approvals",
    "reports": "Reports",
    "power_bi": "Power BI",
    "media": "Media & Communications",
    "meal": "MEAL",
    "memo": "Memo Management",
    "signatures": "Signature Administration",
}

# This is the authoritative application entitlement registry.  Values are XML
# IDs instead of database IDs so the registry remains stable across databases.
# Groups owned by optional addons are resolved lazily and fail closed when the
# addon is not installed.
LHI_APP_ACCESS_GROUPS = {
    "operations": "lhi_security.group_lhi_operations_viewer",
    "hub": "lhi_security.group_lhi_hub_viewer",
    "assets": "lhi_security.group_lhi_asset_viewer",
    "procurement": "lhi_security.group_lhi_procurement_viewer",
    "inventory": "lhi_security.group_lhi_inventory_viewer",
    "fleet": "lhi_security.group_lhi_fleet_viewer",
    "programs_grants": "lhi_security.group_lhi_programme_viewer",
    "approvals": "lhi_security.group_lhi_approvals_viewer",
    "reports": "lhi_security.group_lhi_reports_viewer",
    "power_bi": "lhi_security.group_lhi_powerbi_viewer",
    "media": "lhi_media_communications.group_lhi_media_viewer",
    "meal": "lhi_security.group_lhi_meal_viewer",
    "memo": "lhi_security.group_lhi_employee",
    # This launcher is explicitly the Signature *Administration* application;
    # preparation officers work through their business documents and must not
    # inherit access to webhook/configuration administration.
    "signatures": "lhi_signature_bridge.group_lhi_signature_admin",
}

LHI_APP_SELECTION = list(LHI_APP_LABELS.items())


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

    def _lhi_check_access_target(self):
        """Prevent the helper from becoming a group-enumeration RPC."""
        self.ensure_one()
        if self == self.env.user:
            return
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(_("You may only evaluate your own application access."))

    def has_lhi_app_access(self, app_key):
        """Return whether this user has the positive entitlement for an app.

        Unknown keys and optional groups that are not installed both fail
        closed.  Group evaluation deliberately uses the caller's environment
        and never uses ``sudo()``.
        """
        self._lhi_check_access_target()
        group_xmlid = LHI_APP_ACCESS_GROUPS.get(app_key)
        if not group_xmlid:
            return False

        if self.has_group("lhi_security.group_lhi_erp_admin"):
            return True

        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        return bool(group and group in self.all_group_ids)

    def check_lhi_app_access(self, app_key):
        """Raise a uniform denial for an unknown or unauthorized app key."""
        self.ensure_one()
        if not self.has_lhi_app_access(app_key):
            raise AccessError(
                _("You do not have permission to access this application.")
            )
        return True

    @api.model
    def get_lhi_allowed_apps(self):
        """RPC-safe list of app keys allowed to the current session user."""
        user = self.env.user
        return [
            app_key
            for app_key in LHI_APP_ACCESS_GROUPS
            if user.has_lhi_app_access(app_key)
        ]

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
