# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.lhi_security.models.res_users import LHI_APP_ACCESS_GROUPS


@tagged("post_install", "-at_install")
class TestIntegratedApplicationRBAC(TransactionCase):

    RESTRICTED_APP_MATRIX = {
        "operations": (
            "lhi_security.group_lhi_operations_viewer",
            "lhi_security.group_lhi_operations_officer",
            "lhi_security.group_lhi_operations_manager",
            None,
        ),
        "hub": (
            "lhi_security.group_lhi_hub_viewer",
            "lhi_security.group_lhi_warehouse_officer",
            "lhi_security.group_lhi_hub_manager",
            "lhi.hub.consignment",
        ),
        "assets": (
            "lhi_security.group_lhi_asset_viewer",
            "lhi_security.group_lhi_asset_officer",
            "lhi_security.group_lhi_asset_manager",
            "lhi.asset",
        ),
        "procurement": (
            "lhi_security.group_lhi_procurement_viewer",
            "lhi_security.group_lhi_procurement_officer",
            "lhi_security.group_lhi_procurement_manager",
            "lhi.purchase.request",
        ),
        "inventory": (
            "lhi_security.group_lhi_inventory_viewer",
            "lhi_security.group_lhi_store_officer",
            "lhi_security.group_lhi_inventory_manager",
            "stock.quant",
        ),
        "fleet": (
            "lhi_security.group_lhi_fleet_viewer",
            "lhi_security.group_lhi_fleet_officer",
            "lhi_security.group_lhi_fleet_manager",
            "lhi.fleet.trip",
        ),
        "programs_grants": (
            "lhi_security.group_lhi_programme_viewer",
            "lhi_security.group_lhi_project_officer",
            "lhi_security.group_lhi_project_manager",
            "lhi.project",
        ),
        "approvals": (
            "lhi_security.group_lhi_approvals_viewer",
            "lhi_security.group_lhi_executive_approver",
            "lhi_security.group_lhi_approvals_manager",
            "lhi.approval.matrix",
        ),
        "reports": (
            "lhi_security.group_lhi_reports_viewer",
            "lhi_security.group_lhi_reports_officer",
            "lhi_security.group_lhi_reports_manager",
            "lhi.reporting.job",
        ),
        "power_bi": (
            "lhi_security.group_lhi_powerbi_viewer",
            "lhi_security.group_lhi_powerbi_officer",
            "lhi_security.group_lhi_powerbi_manager",
            "lhi.powerbi.report",
        ),
        "media": (
            "lhi_media_communications.group_lhi_media_viewer",
            "lhi_media_communications.group_lhi_media_officer",
            "lhi_media_communications.group_lhi_media_manager",
            "lhi.media.request",
        ),
        "meal": (
            "lhi_security.group_lhi_meal_viewer",
            "lhi_security.group_lhi_meal_officer",
            "lhi_security.group_lhi_meal_manager",
        ),
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Widget = cls.env["lhi.dashboard.widget"]
        cls.james = new_test_user(
            cls.env,
            login="james.bassey.rbac",
            name="James Bassey RBAC Regression",
            groups=(
                "base.group_user,lhi_security.group_lhi_employee,"
                "lhi_security.group_lhi_warehouse_officer"
            ),
        )
        cls.employee = new_test_user(
            cls.env,
            login="ordinary.employee.rbac",
            groups="base.group_user,lhi_security.group_lhi_employee",
        )

    def _dashboard_keys(self, user):
        return {
            app["key"]
            for app in self.Widget.with_user(user).get_accessible_apps()["apps"]
        }

    def _visible_menu_ids(self, user):
        return self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def _assert_action_allowed(self, xmlid, user):
        action = self.env.ref(xmlid)
        self.assertTrue(action.with_user(user)._get_action_dict())

    def _assert_action_denied(self, xmlid, user):
        with self.assertRaises(AccessError):
            self.env.ref(xmlid).with_user(user)._get_action_dict()

    def test_james_bassey_warehouse_officer_regression(self):
        """Warehouse access must never leak Operations or Programs visibility."""
        allowed = set(self.james.get_lhi_allowed_apps())
        self.assertTrue({"hub", "inventory", "memo"} <= allowed)
        self.assertTrue(
            {"operations", "programs_grants", "assets", "procurement"}.isdisjoint(allowed)
        )

        # Dashboard and sidebar use this same server-authorized payload.
        dashboard_keys = self._dashboard_keys(self.james)
        self.assertTrue({"hub", "inventory", "memo"} <= dashboard_keys)
        self.assertTrue(
            {"operations", "programs_grants", "assets", "procurement"}.isdisjoint(
                dashboard_keys
            )
        )

        visible = self._visible_menu_ids(self.james)
        for xmlid in (
            "lhi_hub_management.menu_lhi_hub",
            "stock.menu_stock_root",
            "lhi_memo_management.menu_lhi_memo_root",
        ):
            self.assertIn(self.env.ref(xmlid).id, visible, xmlid)
        for xmlid in (
            "lhi_dashboard.menu_lhi_operations_hub",
            "lhi_base.menu_lhi_root",
            "lhi_asset_management.menu_lhi_asset",
            "lhi_purchase_request.menu_lhi_procurement_root",
        ):
            self.assertNotIn(self.env.ref(xmlid).id, visible, xmlid)

        self._assert_action_allowed(
            "lhi_hub_management.action_lhi_hub_dashboard", self.james
        )
        self._assert_action_denied(
            "lhi_dashboard.action_lhi_operations_hub", self.james
        )
        self._assert_action_denied("lhi_base.action_lhi_project", self.james)
        self.assertIsInstance(
            self.env["stock.warehouse"]
            .with_user(self.james)
            .get_lhi_hub_dashboard_data(),
            dict,
        )
        with self.assertRaises(AccessError):
            self.Widget.with_user(self.james).get_accessible_operations()
        with self.assertRaises(AccessError):
            self.env["lhi.asset"].with_user(self.james).get_asset_dashboard_data()

    def test_ordinary_employee_sees_only_memo_of_restricted_apps(self):
        self.assertEqual(set(self.employee.get_lhi_allowed_apps()), {"memo"})
        self.assertEqual(self._dashboard_keys(self.employee), {"memo"})
        visible = self._visible_menu_ids(self.employee)
        self.assertIn(self.env.ref("lhi_memo_management.menu_lhi_memo_root").id, visible)

        definitions = {
            key: menu_xmlid
            for key, _label, menu_xmlid, _icon in self.Widget._LHI_APP_DEFINITIONS
        }
        for app_key in self.RESTRICTED_APP_MATRIX:
            menu = self.env.ref(definitions[app_key])
            self.assertNotIn(menu.id, visible, app_key)
            if menu.action:
                with self.assertRaises(AccessError, msg=app_key):
                    menu.action.with_user(self.employee)._get_action_dict()

    def test_every_restricted_application_role_and_surface_matrix(self):
        definitions = {
            key: menu_xmlid
            for key, _label, menu_xmlid, _icon in self.Widget._LHI_APP_DEFINITIONS
        }
        for index, (app_key, role_data) in enumerate(
            self.RESTRICTED_APP_MATRIX.items()
        ):
            viewer_xmlid, officer_xmlid, manager_xmlid, model_name = role_data
            viewer = new_test_user(
                self.env,
                login=f"rbac.matrix.viewer.{index}",
                groups=f"base.group_user,{viewer_xmlid}",
            )
            officer = new_test_user(
                self.env,
                login=f"rbac.matrix.officer.{index}",
                groups=f"base.group_user,{officer_xmlid}",
            )
            manager = new_test_user(
                self.env,
                login=f"rbac.matrix.manager.{index}",
                groups=f"base.group_user,{manager_xmlid}",
            )
            for user in (viewer, officer, manager):
                self.assertTrue(user.has_lhi_app_access(app_key), app_key)

            menu = self.env.ref(definitions[app_key])
            self.assertIn(menu.id, self._visible_menu_ids(viewer), app_key)
            self.assertIn(app_key, self._dashboard_keys(viewer), app_key)
            if menu.action:
                self.assertTrue(
                    menu.action.with_user(viewer)._get_action_dict(), app_key
                )

            if model_name:
                model = self.env[model_name].with_user(viewer)
                self.assertTrue(
                    model.check_access_rights("read", raise_exception=False), app_key
                )
                self.assertFalse(
                    model.check_access_rights("write", raise_exception=False), app_key
                )

    def test_memo_and_signature_administration_exceptions(self):
        self.assertTrue(self.employee.has_lhi_app_access("memo"))
        self.assertFalse(self.employee.has_lhi_app_access("signatures"))
        signature_admin = new_test_user(
            self.env,
            login="rbac.signature.administrator",
            groups=(
                "base.group_user,"
                "lhi_signature_bridge.group_lhi_signature_admin"
            ),
        )
        self.assertTrue(signature_admin.has_lhi_app_access("signatures"))
        menu = self.env.ref("lhi_signature_bridge.menu_lhi_opensign")
        self.assertIn(menu.id, self._visible_menu_ids(signature_admin))
        signature_action = self.env.ref(
            "lhi_signature_bridge.action_lhi_opensign_request"
        )
        with self.assertRaises(AccessError):
            signature_action.with_user(self.employee)._get_action_dict()
        self.assertTrue(signature_action.with_user(signature_admin)._get_action_dict())

    def test_programme_viewer_is_read_only_and_does_not_inherit_operations(self):
        user = new_test_user(
            self.env,
            login="programme.viewer.rbac",
            groups="base.group_user,lhi_security.group_lhi_programme_viewer",
        )
        self.assertTrue(user.has_lhi_app_access("programs_grants"))
        self.assertFalse(user.has_lhi_app_access("operations"))
        self._assert_action_allowed("lhi_base.action_lhi_project", user)
        self._assert_action_denied("lhi_dashboard.action_lhi_operations_hub", user)
        Project = self.env["lhi.project"].with_user(user)
        self.assertTrue(Project.check_access_rights("read", raise_exception=False))
        self.assertFalse(Project.check_access_rights("write", raise_exception=False))

    def test_operations_viewer_does_not_inherit_hub(self):
        user = new_test_user(
            self.env,
            login="operations.viewer.rbac",
            groups="base.group_user,lhi_security.group_lhi_operations_viewer",
        )
        self.assertTrue(user.has_lhi_app_access("operations"))
        self.assertFalse(user.has_lhi_app_access("hub"))
        self._assert_action_allowed("lhi_dashboard.action_lhi_operations_hub", user)
        self._assert_action_denied(
            "lhi_hub_management.action_lhi_hub_dashboard", user
        )

    def test_asset_officer_can_import_without_cross_application_grants(self):
        user = new_test_user(
            self.env,
            login="asset.officer.rbac",
            groups="base.group_user,lhi_security.group_lhi_asset_officer",
        )
        self.assertTrue(user.has_lhi_app_access("assets"))
        self.assertFalse(user.has_lhi_app_access("hub"))
        self.assertFalse(user.has_lhi_app_access("operations"))
        self.assertTrue(
            self.env["lhi.asset.import.wizard"]
            .with_user(user)
            .check_access_rights("create", raise_exception=False)
        )

    def test_erp_administrator_has_every_app_and_action(self):
        administrator = self.env.ref("base.user_admin")
        self.assertEqual(
            set(administrator.get_lhi_allowed_apps()), set(LHI_APP_ACCESS_GROUPS)
        )
        self.assertEqual(self._dashboard_keys(administrator), set(LHI_APP_ACCESS_GROUPS))
        for _key, _label, menu_xmlid, _icon in self.Widget._LHI_APP_DEFINITIONS:
            menu = self.env.ref(menu_xmlid)
            self.assertIn(menu.id, self._visible_menu_ids(administrator), menu_xmlid)
            if menu.action:
                self.assertTrue(menu.action.with_user(administrator)._get_action_dict())
