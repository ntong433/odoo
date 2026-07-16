from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestResultsFramework(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Test Project',
            'status': 'draft'
        })
        cls.framework = cls.env['lhi.results.framework'].create({
            'name': 'Global Framework 2030',
            'project_id': cls.project.id
        })
        cls.goal = cls.env['lhi.results.element'].create({
            'name': 'Goal 1',
            'framework_id': cls.framework.id,
            'element_type': 'goal'
        })
        cls.outcome = cls.env['lhi.results.element'].create({
            'name': 'Outcome 1',
            'framework_id': cls.framework.id,
            'element_type': 'outcome',
            'parent_id': cls.goal.id
        })

    def test_indicator_creation(self):
        indicator = self.env['lhi.indicator'].create({
            'name': 'Number of beneficiaries',
            'element_id': self.outcome.id,
            'target': 1000,
            'unit': 'people',
            'frequency': 'monthly'
        })
        self.assertEqual(indicator.project_id.id, self.project.id)
        self.assertEqual(indicator.progress_percentage, 0.0)
