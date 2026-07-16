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
        """ Test that user can get user widgets """
        widgets = self.Widget.with_user(self.user).get_user_widgets()
        self.assertTrue(any(w['registry_key'] == 'test.widget.1' for w in widgets))

    def test_announcement_visibility(self):
        """ Test that active announcements are retrieved """
        announcements = self.Announcement.with_user(self.user).get_active_announcements()
        self.assertTrue(any(a['title'] == 'Test Announcement' for a in announcements))
