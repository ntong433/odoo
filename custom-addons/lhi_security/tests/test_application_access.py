# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.lhi_security.models.res_users import LHI_APP_ACCESS_GROUPS


@tagged("post_install", "-at_install")
class TestLhiApplicationAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.no_access = new_test_user(
            cls.env,
            login="lhi_rbac_no_access",
            groups="base.group_user,lhi_security.group_lhi_employee",
        )
        cls.operations_viewer = new_test_user(
            cls.env,
            login="lhi_rbac_operations_viewer",
            groups="base.group_user,lhi_security.group_lhi_operations_viewer",
        )
        cls.operations_officer = new_test_user(
            cls.env,
            login="lhi_rbac_operations_officer",
            groups="base.group_user,lhi_security.group_lhi_operations_officer",
        )
        cls.operations_manager = new_test_user(
            cls.env,
            login="lhi_rbac_operations_manager",
            groups="base.group_user,lhi_security.group_lhi_operations_manager",
        )
        cls.programme_viewer = new_test_user(
            cls.env,
            login="lhi_rbac_programme_viewer",
            groups="base.group_user,lhi_security.group_lhi_programme_viewer",
        )

    def test_unknown_key_fails_closed(self):
        self.assertFalse(self.no_access.has_lhi_app_access("unknown_application"))
        with self.assertRaises(AccessError):
            self.no_access.check_lhi_app_access("unknown_application")

    def test_role_hierarchy_and_application_independence(self):
        self.assertTrue(self.operations_viewer.has_lhi_app_access("operations"))
        self.assertTrue(self.operations_officer.has_lhi_app_access("operations"))
        self.assertTrue(self.operations_manager.has_lhi_app_access("operations"))
        self.assertFalse(self.operations_viewer.has_lhi_app_access("hub"))
        self.assertFalse(self.operations_officer.has_lhi_app_access("hub"))
        self.assertFalse(self.programme_viewer.has_lhi_app_access("operations"))
        self.assertFalse(self.programme_viewer.has_lhi_app_access("hub"))

    def test_no_access_and_memo_exception(self):
        allowed = set(self.no_access.get_lhi_allowed_apps())
        self.assertEqual(allowed, {"memo"})
        self.assertTrue(self.no_access.has_lhi_app_access("memo"))
        self.assertFalse(self.no_access.has_lhi_app_access("programs_grants"))

    def test_erp_administrator_has_every_registered_application(self):
        administrator = self.env.ref("base.user_admin")
        self.assertTrue(administrator.has_group("lhi_security.group_lhi_erp_admin"))
        self.assertEqual(
            set(administrator.get_lhi_allowed_apps()),
            set(LHI_APP_ACCESS_GROUPS),
        )
        for group_xmlid in (
            "lhi_security.group_lhi_operations_manager",
            "lhi_security.group_lhi_hub_manager",
            "lhi_security.group_lhi_asset_manager",
            "lhi_security.group_lhi_procurement_manager",
            "lhi_security.group_lhi_inventory_manager",
            "lhi_security.group_lhi_fleet_manager",
            "lhi_security.group_lhi_project_manager",
            "lhi_security.group_lhi_approvals_manager",
            "lhi_security.group_lhi_reports_manager",
            "lhi_security.group_lhi_powerbi_manager",
            "lhi_security.group_lhi_meal_manager",
            "lhi_security.group_lhi_hr_manager",
        ):
            self.assertTrue(administrator.has_group(group_xmlid), group_xmlid)

    def test_direct_action_is_denied_server_side(self):
        action = self.env["ir.actions.act_window"].create(
            {
                "name": "RBAC Operations Test",
                "res_model": "lhi.office",
                "view_mode": "list",
                "lhi_app_key": "operations",
            }
        )
        with self.assertRaises(AccessError):
            action.with_user(self.no_access)._get_action_dict()
        self.assertEqual(
            action.with_user(self.operations_viewer)._get_action_dict()["res_model"],
            "lhi.office",
        )

    def test_menu_cache_reflects_role_change(self):
        action = self.env["ir.actions.act_window"].create(
            {
                "name": "RBAC Menu Test",
                "res_model": "lhi.office",
                "view_mode": "list",
                "lhi_app_key": "operations",
            }
        )
        menu = self.env["ir.ui.menu"].create(
            {
                "name": "RBAC Operations Menu Test",
                "action": f"ir.actions.act_window,{action.id}",
                "group_ids": [
                    (6, 0, [self.env.ref("lhi_security.group_lhi_operations_viewer").id])
                ],
                "lhi_app_key": "operations",
            }
        )
        visible_before = self.env["ir.ui.menu"].with_user(self.no_access)._visible_menu_ids()
        self.assertNotIn(menu.id, visible_before)

        self.no_access.write(
            {
                "group_ids": [
                    (4, self.env.ref("lhi_security.group_lhi_operations_viewer").id)
                ]
            }
        )
        visible_after = self.env["ir.ui.menu"].with_user(self.no_access)._visible_menu_ids()
        self.assertIn(menu.id, visible_after)

    def test_programme_viewer_acl_is_read_only(self):
        Project = self.env["lhi.project"].with_user(self.programme_viewer)
        self.assertTrue(Project.check_access_rights("read", raise_exception=False))
        self.assertFalse(Project.check_access_rights("write", raise_exception=False))
        self.assertFalse(
            self.env["lhi.project"]
            .with_user(self.no_access)
            .check_access_rights("read", raise_exception=False)
        )
