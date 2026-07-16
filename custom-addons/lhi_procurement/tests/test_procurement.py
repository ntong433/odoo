from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestProcurement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.vendor1 = cls.env['lhi.vendor'].create({'name': 'V1'})
        cls.vendor2 = cls.env['lhi.vendor'].create({'name': 'V2'})
        
        cls.pr = cls.env['lhi.purchase.request'].create({
            'justification': 'Need stuff',
            'required_date': '2030-01-01',
            'state': 'approved'
        })
        
    def test_sourcing_lifecycle_lowest_responsive(self):
        sourcing = self.env['lhi.sourcing'].create({
            'title': 'Test Sourcing',
            'request_id': self.pr.id,
            'sourcing_type': 'rfq',
            'evaluation_method': 'lowest_responsive'
        })
        
        # Test evaluator COI
        evaluator = self.env['lhi.sourcing.evaluator'].create({
            'sourcing_id': sourcing.id,
            'user_id': self.env.user.id
        })
        
        sourcing.action_publish()
        sourcing.action_bid_opening()
        
        # Fails because no COI declared
        with self.assertRaises(ValidationError):
            sourcing.action_technical_evaluation()
            
        evaluator.action_declare_no_conflict()
        sourcing.action_technical_evaluation()
        
        # Add bids
        bid1 = self.env['lhi.bid'].create({
            'sourcing_id': sourcing.id,
            'vendor_id': self.vendor1.id,
            'technical_compliant': True,
            'financial_amount': 5000,
            'state': 'submitted'
        })
        
        bid2 = self.env['lhi.bid'].create({
            'sourcing_id': sourcing.id,
            'vendor_id': self.vendor2.id,
            'technical_compliant': True,
            'financial_amount': 4000,
            'state': 'submitted'
        })
        
        sourcing.action_financial_evaluation()
        sourcing.action_recommend()
        
        self.assertEqual(bid2.state, 'recommended')
        self.assertEqual(bid1.state, 'submitted')
        
        sourcing.action_award()
        self.assertEqual(bid2.state, 'awarded')
        self.assertEqual(sourcing.state, 'awarded')

    def test_sourcing_lifecycle_weighted(self):
        sourcing = self.env['lhi.sourcing'].create({
            'title': 'Test Sourcing Weighted',
            'request_id': self.pr.id,
            'sourcing_type': 'tender',
            'evaluation_method': 'weighted',
            'tech_weight': 60,
            'fin_weight': 40
        })
        
        bid1 = self.env['lhi.bid'].create({
            'sourcing_id': sourcing.id,
            'vendor_id': self.vendor1.id,
            'technical_compliant': True,
            'technical_score': 90,
            'financial_amount': 10000,
            'state': 'submitted'
        })
        
        bid2 = self.env['lhi.bid'].create({
            'sourcing_id': sourcing.id,
            'vendor_id': self.vendor2.id,
            'technical_compliant': True,
            'technical_score': 70,
            'financial_amount': 8000,
            'state': 'submitted'
        })
        
        sourcing.write({'state': 'financial'})
        sourcing.action_recommend()
        
        # bid1: tech(90 * 0.6 = 54) + fin(8000/10000 * 100 = 80 * 0.4 = 32) = 86
        # bid2: tech(70 * 0.6 = 42) + fin(8000/8000 * 100 = 100 * 0.4 = 40) = 82
        self.assertEqual(bid1.state, 'recommended')
        self.assertEqual(bid2.state, 'submitted')
