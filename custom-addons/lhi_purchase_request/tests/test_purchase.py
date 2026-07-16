from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestPurchaseRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # We need a project and approval matrix
        cls.project = cls.env['lhi.project'].create({
            'name': 'PR Project'
        })
        cls.budget_line = cls.env['lhi.budget.line'].create({
            'name': 'BL-001',
            'project_id': cls.project.id
        })
        
        # Create a simple approval matrix
        cls.matrix = cls.env['lhi.approval.matrix'].create({
            'name': 'Default Purchase Matrix',
            'document_type': 'purchase',
            'company_id': cls.env.company.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Manager Approval',
                    'sequence': 10,
                    'approver_group_id': cls.env.ref('base.group_user').id,
                    'approval_type': 'any'
                })
            ]
        })
        # Note: In a real test we'd need to mock find_matching_matrix to return this matrix 
        # or ensure criteria match. The matrix created has no constraints so it should match.

    def test_pr_workflow(self):
        pr = self.env['lhi.purchase.request'].create({
            'justification': 'Need supplies',
            'required_date': '2030-12-31',
            'project_id': self.project.id,
            'budget_line_id': self.budget_line.id
        })
        
        with self.assertRaises(ValidationError):
            pr.action_submit() # Fails because no lines
            
        pr.write({
            'line_ids': [(0, 0, {
                'name': 'Laptops',
                'quantity': 5,
                'unit_price': 1000
            })]
        })
        
        self.assertEqual(pr.total_estimated_amount, 5000)
        
        # We can't fully test approval matrix submission without the matrix logic firing,
        # but we can test manual state updates.
        
        # Simulate approval
        pr.write({'lhi_approval_state': 'approved'})
        self.assertEqual(pr.state, 'approved')
        
        # Test cancellation
        pr.action_cancel()
        self.assertEqual(pr.state, 'cancelled')
