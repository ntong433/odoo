# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


_MENU_APP_KEYS = {
    "lhi_dashboard.menu_lhi_operations_hub": "operations",
    "lhi_hub_management.menu_lhi_hub": "hub",
    "lhi_asset_management.menu_lhi_asset": "assets",
    "lhi_purchase_request.menu_lhi_procurement_root": "procurement",
    "stock.menu_stock_root": "inventory",
    "fleet.menu_root": "fleet",
    "lhi_base.menu_lhi_root": "programs_grants",
    "lhi_approval_matrix.menu_lhi_approvals_root": "approvals",
    "lhi_reporting_hub.menu_lhi_reporting_hub_root": "reports",
    "lhi_powerbi.menu_lhi_powerbi_root": "power_bi",
    "lhi_media_communications.menu_lhi_media_root": "media",
    "lhi_results_framework.menu_lhi_meal_root": "meal",
    "lhi_memo_management.menu_lhi_memo_root": "memo",
    "lhi_signature_bridge.menu_lhi_opensign": "signatures",
    "lhi_leave_bridge.menu_lhi_leave_root": "hr_leave",
}

_GROUP_APP_KEYS = {
    "lhi_security.group_lhi_operations_viewer": "operations",
    "lhi_security.group_lhi_operations_officer": "operations",
    "lhi_security.group_lhi_operations_manager": "operations",
    "lhi_security.group_lhi_hub_viewer": "hub",
    "lhi_security.group_lhi_warehouse_officer": "hub",
    "lhi_security.group_lhi_hub_manager": "hub",
    "lhi_security.group_lhi_asset_viewer": "assets",
    "lhi_security.group_lhi_asset_officer": "assets",
    "lhi_security.group_lhi_asset_manager": "assets",
    "lhi_security.group_lhi_procurement_viewer": "procurement",
    "lhi_security.group_lhi_procurement_officer": "procurement",
    "lhi_security.group_lhi_procurement_manager": "procurement",
    "lhi_security.group_lhi_inventory_viewer": "inventory",
    "lhi_security.group_lhi_store_officer": "inventory",
    "lhi_security.group_lhi_inventory_manager": "inventory",
    "lhi_security.group_lhi_fleet_viewer": "fleet",
    "lhi_security.group_lhi_fleet_officer": "fleet",
    "lhi_security.group_lhi_fleet_manager": "fleet",
    "lhi_security.group_lhi_programme_viewer": "programs_grants",
    "lhi_security.group_lhi_project_officer": "programs_grants",
    "lhi_security.group_lhi_project_manager": "programs_grants",
    "lhi_security.group_lhi_approvals_viewer": "approvals",
    "lhi_security.group_lhi_executive_approver": "approvals",
    "lhi_security.group_lhi_approvals_manager": "approvals",
    "lhi_security.group_lhi_reports_viewer": "reports",
    "lhi_security.group_lhi_reports_manager": "reports",
    "lhi_security.group_lhi_powerbi_viewer": "power_bi",
    "lhi_security.group_lhi_powerbi_manager": "power_bi",
    "lhi_security.group_lhi_meal_viewer": "meal",
    "lhi_security.group_lhi_meal_officer": "meal",
    "lhi_security.group_lhi_meal_manager": "meal",
    "lhi_security.group_lhi_hr_viewer": "hr_leave",
    "lhi_security.group_lhi_hr_officer": "hr_leave",
    "lhi_security.group_lhi_hr_manager": "hr_leave",
    "lhi_media_communications.group_lhi_media_viewer": "media",
    "lhi_memo_management.group_lhi_memo_user": "memo",
    "lhi_signature_bridge.group_lhi_signature_admin": "signatures",
}


def _xmlid(record):
    return record.get_external_id().get(record.id) if record else None


def _menu_app_key(menu):
    current = menu
    while current:
        if current.lhi_app_key:
            return current.lhi_app_key
        if app_key := _MENU_APP_KEYS.get(_xmlid(current)):
            return app_key
        current = current.parent_id
    return None


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # These six maintained records are non-application dashboard utilities.
    # Explicit classification prevents an empty group list from being treated
    # as public by accident while retaining the intended internal dashboard.
    public_widgets = env["lhi.dashboard.widget"].browse(
        [
            record.id
            for xmlid in (
                "lhi_dashboard.widget_announcements",
                "lhi_dashboard.widget_my_tasks",
                "lhi_dashboard.widget_my_approvals",
                "lhi_dashboard.widget_quick_actions",
                "lhi_dashboard.widget_notifications",
                "lhi_dashboard.widget_accessible_modules",
            )
            if (record := env.ref(xmlid, raise_if_not_found=False))
        ]
    )
    if public_widgets:
        public_widgets.write(
            {"is_public_internal": True, "app_key": False, "group_ids": [(5, 0, 0)]}
        )

    group_key_by_id = {
        group.id: app_key
        for xmlid, app_key in _GROUP_APP_KEYS.items()
        if (group := env.ref(xmlid, raise_if_not_found=False))
    }
    migrated = deactivated = 0
    mappings = env["lhi.sidebar.role.mapping"].with_context(active_test=False).search([])
    for mapping in mappings:
        if mapping.app_key:
            continue
        app_key = _menu_app_key(mapping.menu_id)
        if not app_key and mapping.group_id:
            app_key = group_key_by_id.get(mapping.group_id.id)
        if app_key:
            mapping.write({"app_key": app_key})
            migrated += 1
        elif mapping.active:
            # Unknown legacy mappings cannot safely grant a restricted app.
            mapping.write({"active": False})
            deactivated += 1

    _logger.info(
        "LHI dashboard RBAC migration classified %s widgets, migrated %s "
        "sidebar mappings, and fail-closed %s unknown mappings",
        len(public_widgets),
        migrated,
        deactivated,
    )
