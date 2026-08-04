# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Deactivate the Leave frontend menus if present
    menu_xmlids = (
        "lhi_leave_bridge.menu_lhi_leave_root",
        "lhi_leave_bridge.menu_lhi_leave_balances",
        "lhi_leave_bridge.menu_lhi_leave_staff",
    )
    menus_deactivated = 0
    for xmlid in menu_xmlids:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu.active:
            menu.write({"active": False})
            menus_deactivated += 1

    # 2. Clear lhi_app_key = 'hr_leave' on any remaining ir.ui.menu records
    menus_cleared = 0
    if "lhi_app_key" in env["ir.ui.menu"]._fields:
        hr_leave_menus = env["ir.ui.menu"].with_context(active_test=False).search([("lhi_app_key", "=", "hr_leave")])
        if hr_leave_menus:
            menus_cleared = len(hr_leave_menus)
            hr_leave_menus.write({"lhi_app_key": False})

    # 3. Clear lhi_app_key = 'hr_leave' on any action records
    actions_cleared = 0
    if "lhi_app_key" in env["ir.actions.actions"]._fields:
        hr_leave_actions = env["ir.actions.actions"].search([("lhi_app_key", "=", "hr_leave")])
        if hr_leave_actions:
            actions_cleared = len(hr_leave_actions)
            hr_leave_actions.write({"lhi_app_key": False})

    # 4. Remove any lhi.dashboard.widget records referencing hr_leave
    widgets_deleted = 0
    if "lhi.dashboard.widget" in env:
        hr_leave_widgets = env["lhi.dashboard.widget"].with_context(active_test=False).search([("app_key", "=", "hr_leave")])
        if hr_leave_widgets:
            widgets_deleted = len(hr_leave_widgets)
            hr_leave_widgets.unlink()

    # 5. Remove any lhi.sidebar.role.mapping records referencing hr_leave
    mappings_deleted = 0
    if "lhi.sidebar.role.mapping" in env:
        hr_leave_mappings = env["lhi.sidebar.role.mapping"].with_context(active_test=False).search([("app_key", "=", "hr_leave")])
        if hr_leave_mappings:
            mappings_deleted = len(hr_leave_mappings)
            hr_leave_mappings.unlink()

    _logger.info(
        "LHI HR & Leave cleanup migration 19.0.2.1.0 completed: "
        "deactivated %s menus, cleared %s menu app_keys, cleared %s action app_keys, "
        "deleted %s widgets, deleted %s sidebar mappings.",
        menus_deactivated,
        menus_cleared,
        actions_cleared,
        widgets_deleted,
        mappings_deleted,
    )
