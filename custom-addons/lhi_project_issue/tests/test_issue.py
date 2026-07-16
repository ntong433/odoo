from odoo.tests.common import TransactionCase

class TestProjectIssue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Issue Project'
        })

    def test_issue_workflow(self):
        issue = self.env['lhi.project.issue'].create({
            'name': 'Supplier Delay',
            'project_id': self.project.id,
            'owner_id': self.env.user.id,
            'description': 'Main supplier is delayed by 2 weeks'
        })
        
        self.assertEqual(issue.state, 'draft')
        issue.action_open()
        self.assertEqual(issue.state, 'open')
        issue.action_resolve()
        self.assertEqual(issue.state, 'resolved')
        
        issue.action_close()
        self.assertEqual(issue.state, 'closed')
        self.assertEqual(issue.closure_approval_id.id, self.env.user.id)
