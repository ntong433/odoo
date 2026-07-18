from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestLhiLoginTemplate(TransactionCase):
    def test_login_template_uses_native_provider_context(self):
        view = self.env.ref("lhi_web_shell.lhi_login_override")
        architecture = view.arch_db
        self.assertIn("provider.get('auth_link')", architecture)
        self.assertNotIn("microsoft_provider_id", architecture)
        self.assertNotIn("/auth_oauth/signin", architecture)
        self.assertIn("container-fluid p-0 lhi-login-host", architecture)
        self.assertIn("lhi-login-visual", architecture)
        self.assertIn("lhi-login-panel", architecture)
        self.assertIn("lhi-microsoft-button", architecture)
        self.assertIn("fa fa-windows", architecture)
        self.assertNotIn("fa-sign-in", architecture)
        self.assertLess(
            architecture.index("oe_login_form"),
            architecture.index("lhi-login-divider"),
        )

    def test_auth_oauth_is_an_installed_dependency(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "auth_oauth")], limit=1
        )
        self.assertEqual(module.state, "installed")

    def test_apps_are_system_administrator_only(self):
        ordinary_user = new_test_user(
            self.env,
            login="lhi_apps_security_user",
            groups="base.group_user",
        )
        apps_menu = self.env.ref("base.menu_apps")
        apps_action = self.env.ref("base.open_module_tree")
        system_group = self.env.ref("base.group_system")
        self.assertEqual(apps_menu.group_ids, system_group)
        self.assertEqual(apps_action.group_ids, system_group)
        self.assertFalse(
            self.env["ir.module.module"].with_user(ordinary_user).check_access_rights(
                "read", raise_exception=False
            )
        )
