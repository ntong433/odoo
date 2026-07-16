from odoo.tests.common import TransactionCase

class TestProcurementCommitment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.project = cls.env['lhi.project'].create({'name': 'Commitment Project'})
        
    def test_commitment_creation_and_release(self):
        pr = self.env['lhi.purchase.request'].create({
            'justification': 'Servers',
            'required_date': '2030-12-31',
            'project_id': self.project.id,
            'line_ids': [(0, 0, {
                'name': 'Server',
                'quantity': 2,
                'unit_price': 5000
            })]
        })
        
        self.assertFalse(pr.commitment_id)
        
        # Approve PR
        pr.write({'lhi_approval_state': 'approved'})
        
        # Commitment should be created
        self.assertTrue(pr.commitment_id)
        self.assertEqual(pr.commitment_id.amount_reserved, 10000)
        self.assertEqual(pr.commitment_id.state, 'reserved')
        
        # Cancel PR -> releases commitment
        pr.action_cancel()
        self.assertEqual(pr.commitment_id.state, 'released')
        self.assertEqual(pr.commitment_id.amount_reserved, 0)
