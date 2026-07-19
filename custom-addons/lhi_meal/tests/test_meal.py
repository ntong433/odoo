from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestMeal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Test Project',
            'code': 'MEAL-TEST',
        })
        cls.framework = cls.env['lhi.results.framework'].create({
            'name': 'Global Framework 2030',
            'project_id': cls.project.id
        })
        cls.outcome = cls.env['lhi.results.element'].create({
            'name': 'Outcome 1',
            'framework_id': cls.framework.id,
            'element_type': 'outcome'
        })
        cls.indicator = cls.env['lhi.indicator'].create({
            'name': 'Number of beneficiaries',
            'element_id': cls.outcome.id,
            'target': 1000,
            'unit': 'people',
            'frequency': 'monthly'
        })
        
        # User without sensitive group
        cls.normal_user = cls.env['res.users'].create({
            'name': 'Normal User',
            'login': 'normaluser',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])]
        })
        
        # User with sensitive group
        cls.sensitive_user = cls.env['res.users'].create({
            'name': 'Sensitive User',
            'login': 'sensitiveuser',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('lhi_meal.group_lhi_meal_sensitive').id])]
        })

    def test_meal_data_workflow(self):
        meal_data = self.env['lhi.meal.data'].create({
            'indicator_id': self.indicator.id,
            'achieved_value': 100,
            'narrative': 'Test data'
        })
        self.assertEqual(meal_data.state, 'draft')
        
        meal_data.action_submit()
        self.assertEqual(meal_data.state, 'submitted')
        
        meal_data.action_approve()
        self.assertEqual(meal_data.state, 'approved')
        self.assertEqual(self.indicator.achieved_total, 100.0)
        self.assertEqual(self.indicator.progress_percentage, 10.0)
        
    def test_meal_data_rejection(self):
        meal_data = self.env['lhi.meal.data'].create({
            'indicator_id': self.indicator.id,
            'achieved_value': 50,
            'narrative': 'Test data 2'
        })
        meal_data.action_submit()
        
        with self.assertRaises(ValidationError):
            meal_data.action_reject()  # Should fail because no feedback
            
        meal_data.correction_feedback = 'Needs more detail'
        meal_data.action_reject()
        self.assertEqual(meal_data.state, 'rejected')
        
    def test_sensitive_data_isolation(self):
        sensitive_data = self.env['lhi.meal.data'].create({
            'indicator_id': self.indicator.id,
            'achieved_value': 20,
            'narrative': 'Secret data',
            'is_sensitive': True
        })
        
        normal_env = self.env(user=self.normal_user)
        sensitive_env = self.env(user=self.sensitive_user)
        
        self.assertFalse(normal_env['lhi.meal.data'].search([('id', '=', sensitive_data.id)]))
        self.assertTrue(sensitive_env['lhi.meal.data'].search([('id', '=', sensitive_data.id)]))

    def test_standalone_meal_initiative_submits_without_project(self):
        initiative = self.env['lhi.meal.initiative'].create({
            'name': 'Organization-wide learning review',
            'initiative_type': 'learning',
            'work_context': 'standalone_departmental',
            'date_start': '2026-04-01',
            'date_end': '2026-04-02',
            'purpose': 'Review organizational learning outside a donor project.',
        })
        initiative.action_submit()
        self.assertEqual(initiative.state, 'submitted')

    def test_project_linked_meal_initiative_requires_project(self):
        initiative = self.env['lhi.meal.initiative'].create({
            'name': 'Project baseline',
            'initiative_type': 'baseline',
            'work_context': 'project_linked',
            'date_start': '2026-05-01',
            'date_end': '2026-05-02',
            'purpose': 'Establish project baseline values.',
        })
        with self.assertRaises(ValidationError):
            initiative.action_submit()
