from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestProjectCloseout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Closeout Project'
        })

    def test_closeout_workflow(self):
        closeout = self.env['lhi.project.closeout'].create({
            'project_id': self.project.id,
            'enterprise_financial_figures': 50000,
            'archive_location': 'Digital Drive Z'
        })
        
        self.assertEqual(closeout.state, 'draft')
        closeout.action_start()
        self.assertEqual(closeout.state, 'in_progress')
        closeout.action_review()
        self.assertEqual(closeout.state, 'reviewed')
        
        with self.assertRaises(ValidationError):
            closeout.action_complete()
            
        closeout.programmatic_cleared = True
        closeout.procurement_cleared = True
        closeout.asset_cleared = True
        closeout.partner_cleared = True
        closeout.administrative_cleared = True
        closeout.financial_cleared = True
        
        closeout.action_complete()
        self.assertEqual(closeout.state, 'completed')
        
        # Now we can archive the project
        self.project.active = False
        self.assertFalse(self.project.active)

    def test_project_archive_blocked_without_closeout(self):
        project2 = self.env['lhi.project'].create({'name': 'Another Project'})
        with self.assertRaises(ValidationError):
            project2.active = False
