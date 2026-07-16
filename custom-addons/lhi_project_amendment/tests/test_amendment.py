from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import timedelta
from odoo import fields

class TestProjectAmendment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Amendment Project'
        })

    def test_amendment_workflow(self):
        amendment = self.env['lhi.project.amendment'].create({
            'name': 'No-Cost Extension Q3',
            'project_id': self.project.id,
            'amendment_type': 'no_cost',
            'justification': 'Delays in Q2',
            'original_value': 'End Date: 2030-06-30',
            'proposed_value': 'End Date: 2030-09-30',
            'effective_date': fields.Date.context_today(self.env.user)
        })
        
        self.assertEqual(amendment.state, 'draft')
        amendment.action_submit_internal()
        self.assertEqual(amendment.state, 'internal_review')
        amendment.action_approve_internal()
        self.assertEqual(amendment.state, 'submitted')
        amendment.action_donor_approve()
        self.assertEqual(amendment.state, 'approved')
        
        amendment.action_apply()
        self.assertEqual(amendment.state, 'applied')
        
    def test_future_amendment_apply_fails(self):
        amendment = self.env['lhi.project.amendment'].create({
            'name': 'Future Amendment',
            'project_id': self.project.id,
            'amendment_type': 'budget',
            'justification': 'Need more funds',
            'effective_date': fields.Date.context_today(self.env.user) + timedelta(days=10)
        })
        amendment.action_submit_internal()
        amendment.action_approve_internal()
        amendment.action_donor_approve()
        
        with self.assertRaises(ValidationError):
            amendment.action_apply()
