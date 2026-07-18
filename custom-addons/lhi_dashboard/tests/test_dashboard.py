from odoo.tests.common import TransactionCase, new_test_user


class TestLhiDashboard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Widget = self.env['lhi.dashboard.widget']
        self.Announcement = self.env['lhi.announcement']
        self.user = new_test_user(
            self.env,
            login='lhi_dashboard_test_user',
            groups='base.group_user',
        )

        self.widget_1 = self.Widget.create({
            'name': 'Test Widget',
            'registry_key': 'test.widget.1',
            'active': True,
        })

        self.announcement = self.Announcement.create({
            'name': 'Test Announcement',
            'content': '<p>This is a test</p>',
            'type': 'info',
            'active': True,
        })

    def test_widget_access(self):
        """Only the maintained operational dashboard widgets are returned."""
        widgets = self.Widget.with_user(self.user).get_user_widgets()
        self.assertFalse(any(w['registry_key'] == 'test.widget.1' for w in widgets))
        self.assertTrue(any(w['registry_key'] == 'lhi_dashboard.my_tasks' for w in widgets))
        my_apps = next(
            w for w in widgets
            if w['registry_key'] == 'lhi_dashboard.accessible_modules'
        )
        self.assertEqual(my_apps['col_span'], 12)

    def test_user_without_functional_assignment_has_no_apps(self):
        self.assertEqual(self.Widget.with_user(self.user).get_accessible_apps(), [])

    def test_app_definitions_use_xmlids_and_local_icons(self):
        for key, _label, menu_xmlid, _groups, _departments in self.Widget._LHI_APP_DEFINITIONS:
            self.assertIn('.', menu_xmlid)
            self.assertNotEqual(key, menu_xmlid)

    def test_announcement_visibility(self):
        """ Test that active announcements are retrieved """
        announcements = self.Announcement.with_user(self.user).get_active_announcements()
        self.assertTrue(any(a['title'] == 'Test Announcement' for a in announcements))

    def test_single_canonical_dashboard_client_action(self):
        actions = self.env["ir.actions.client"].search(
            [("tag", "ilike", "lhi_dashboard")]
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions.tag, "lhi_dashboard.dashboard_action")
        self.assertEqual(actions.target, "main")
        menu = self.env.ref("lhi_dashboard.menu_lhi_dashboard_root")
        self.assertEqual(menu.action, actions)
