from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLhiLoginTemplate(TransactionCase):
    def test_login_template_uses_native_provider_context(self):
        view = self.env.ref("lhi_web_shell.lhi_login_override")
        architecture = view.arch_db
        self.assertIn("provider.get('auth_link')", architecture)
        self.assertIn("provider.get('body')", architecture)
        self.assertNotIn("microsoft_provider_id", architecture)
        self.assertNotIn("/auth_oauth/signin", architecture)

    def test_auth_oauth_is_an_installed_dependency(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "auth_oauth")], limit=1
        )
        self.assertEqual(module.state, "installed")
