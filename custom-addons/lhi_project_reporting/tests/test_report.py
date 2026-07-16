from odoo.tests.common import TransactionCase
from odoo import fields

class TestProjectReporting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Reporting Project'
        })

    def test_report_workflow(self):
        report = self.env['lhi.project.report'].create({
            'name': 'Q1 Narrative',
            'project_id': self.project.id,
            'report_type': 'narrative',
            'owner_id': self.env.user.id
        })
        
        self.assertEqual(report.state, 'draft')
        report.action_in_progress()
        self.assertEqual(report.state, 'in_progress')
        
        report.action_review()
        self.assertEqual(report.state, 'review')
        
        report.action_submit()
        self.assertEqual(report.state, 'submitted')
        self.assertEqual(report.submission_date, fields.Date.context_today(self.env.user))
        
        report.action_request_revision()
        self.assertEqual(report.state, 'revised')
        self.assertEqual(report.version, 2)
        
        report.action_approve()
        self.assertEqual(report.state, 'approved')
