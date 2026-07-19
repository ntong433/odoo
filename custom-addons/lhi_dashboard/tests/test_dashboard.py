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
            self.assertFalse(menu_xmlid.isdigit())

    def test_affected_dashboard_actions_resolve(self):
        expected = {
            'meal': ('lhi_results_framework.menu_lhi_meal_root', 'lhi_results_framework.action_lhi_results_framework'),
            'projects': ('lhi_base.menu_lhi_project_root', 'lhi_base.action_lhi_project'),
            'grants': ('lhi_funding_opportunity.menu_lhi_funding_root', 'lhi_funding_opportunity.action_lhi_funding_opportunity'),
            'approvals': ('lhi_approval_matrix.menu_lhi_my_pending_approvals', 'lhi_approval_matrix.action_lhi_my_pending_approvals'),
            'media': ('lhi_media_communications.menu_lhi_media_root', 'lhi_media_communications.action_lhi_media_request'),
        }
        definitions = {item[0]: item for item in self.Widget._LHI_APP_DEFINITIONS}
        for key, (menu_xmlid, action_xmlid) in expected.items():
            self.assertEqual(definitions[key][2], menu_xmlid)
            menu = self.env.ref(menu_xmlid)
            action = self.env.ref(action_xmlid)
            self.assertEqual(menu.action, action)

    def test_functional_assignment_controls_card_visibility(self):
        cases = (
            ('lhi_security.group_lhi_meal_officer', 'meal'),
            ('lhi_security.group_lhi_project_officer', 'projects'),
            ('lhi_security.group_lhi_project_officer', 'grants'),
            ('lhi_security.group_lhi_executive_approver', 'approvals'),
            ('lhi_media_communications.group_lhi_media_viewer', 'media'),
        )
        for index, (group_xmlid, expected_key) in enumerate(cases):
            user = new_test_user(
                self.env,
                login=f'lhi_dashboard_role_user_{index}',
                groups=f'base.group_user,{group_xmlid}',
            )
            keys = {
                app['key']
                for app in self.Widget.with_user(user).get_accessible_apps()
            }
            self.assertIn(expected_key, keys)

    def test_approval_summary_uses_assigned_request_lines(self):
        approver = new_test_user(
            self.env,
            login='lhi_dashboard_approval_summary_user',
            groups='base.group_user,lhi_security.group_lhi_executive_approver',
        )
        summary = self.Widget.with_user(approver).get_my_approval_summary()
        self.assertTrue(summary['available'])
        self.assertEqual(summary['count'], 0)

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
