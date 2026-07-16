from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    entra_object_id = fields.Char(
        string="Canonical Entra Object ID",
        related="user_id.entra_object_id",
        store=True,
        readonly=True,
        index=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_tenant_id = fields.Char(
        related="user_id.entra_tenant_id",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_upn = fields.Char(
        related="user_id.entra_upn",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_account_enabled = fields.Boolean(
        related="user_id.entra_account_enabled",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_manager_object_id = fields.Char(
        related="user_id.entra_manager_object_id",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_last_sync_at = fields.Datetime(
        related="user_id.entra_last_sync_at",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    entra_sync_state = fields.Selection(
        related="user_id.entra_sync_state",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
    identity_source = fields.Selection(
        related="user_id.identity_source",
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
    )
