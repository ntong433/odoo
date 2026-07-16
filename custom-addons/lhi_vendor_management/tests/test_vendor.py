from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestVendorManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_vendor_onboarding(self):
        vendor = self.env['lhi.vendor'].create({
            'name': 'Test Vendor LLC',
            'tin': '123456789',
            'bank_details': 'Bank of Odoo, 12345',
        })
        
        # Test validation on submit without docs
        with self.assertRaises(ValidationError):
            vendor.action_submit_for_review()
            
        # Add doc and submit
        attachment = self.env['ir.attachment'].create({
            'name': 'doc.pdf',
            'datas': 'b3duZXJzaGlw',
            'res_model': 'lhi.vendor',
            'res_id': vendor.id
        })
        vendor.write({'document_ids': [(4, attachment.id)]})
        vendor.action_submit_for_review()
        self.assertEqual(vendor.state, 'under_review')
        
        # Test approval rules
        with self.assertRaises(ValidationError):
            vendor.action_approve() # Fails because due diligence != passed
            
        vendor.write({'due_diligence_status': 'passed'})
        vendor.action_approve()
        
        self.assertEqual(vendor.state, 'approved')
        self.assertTrue(vendor.expiry_date)
        
        # Suspend
        vendor.action_suspend()
        self.assertEqual(vendor.state, 'suspended')
