# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError, UserError


class TestProtectedAdministrator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.group_erp_admin = cls.env.ref('lhi_security.group_lhi_erp_admin')
        cls.group_employee = cls.env.ref('lhi_security.group_lhi_employee')

        # Ordinary operational user without admin privileges
        cls.standard_user = new_test_user(
            cls.env,
            login='standard_ops_user',
            name='Standard Operational User',
            groups='base.group_user,lhi_security.group_lhi_employee',
        )

    def test_protected_administrator_identity_detection(self):
        """Verify _lhi_is_protected_administrator accurately detects protected root."""
        self.assertTrue(self.admin_user._lhi_is_protected_administrator())
        self.assertTrue(self.env.ref('base.user_root')._lhi_is_protected_administrator())
        self.assertFalse(self.standard_user._lhi_is_protected_administrator())

    def test_protected_administrator_acl_bypass(self):
        """Verify protected administrator bypasses model ACL restrictions."""
        # Check against a restricted model
        has_access_admin = self.env['ir.model.access'].with_user(self.admin_user).check('lhi.office', 'read', False)
        self.assertTrue(has_access_admin)

        has_write_admin = self.env['ir.model.access'].with_user(self.admin_user).check('lhi.office', 'write', False)
        self.assertTrue(has_write_admin)

    def test_protected_administrator_record_rule_bypass(self):
        """Verify protected administrator receives empty record rules for unrestricted query access."""
        rules_admin = self.env['ir.rule'].with_user(self.admin_user)._get_rules('lhi.office', mode='read')
        self.assertFalse(rules_admin)

    def test_protected_administrator_menu_visibility(self):
        """Verify protected administrator sees all active menus."""
        active_menus = self.env['ir.ui.menu'].search([('active', '=', True)])
        visible_menus_admin = self.env['ir.ui.menu'].with_user(self.admin_user)._visible_menu_ids()
        self.assertEqual(visible_menus_admin, frozenset(active_menus.ids))

    def test_protected_administrator_dashboard_apps(self):
        """Verify protected administrator gets all installed app cards on dashboard launcher."""
        widget_model = self.env['lhi.dashboard.widget'].with_user(self.admin_user)
        accessible_apps = widget_model.get_user_widgets()
        self.assertTrue(accessible_apps)

    def test_approval_matrix_candidate_exclusion(self):
        """Verify protected administrator is excluded from approval matrix candidate approvers."""
        stage = self.env['lhi.approval.matrix.line'].new({
            'name': 'Test Stage',
            'approver_group_id': self.group_erp_admin.id,
        })
        candidates = stage._lhi_resolve_approver_users(request=False)
        self.assertNotIn(self.admin_user, candidates)

    def test_protected_account_hardening(self):
        """Verify protected administrator account cannot be deleted or archived."""
        with self.assertRaises(UserError):
            self.admin_user.unlink()

        with self.assertRaises(UserError):
            self.admin_user.action_archive()

        with self.assertRaises(UserError):
            self.admin_user.write({'active': False})

    def test_non_root_user_modification_prevention(self):
        """Verify ordinary non-root users cannot modify protected root account."""
        with self.assertRaises(AccessError):
            self.admin_user.with_user(self.standard_user).write({'name': 'Attacked Admin Name'})
