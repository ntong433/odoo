from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestLegacyAccountingBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.vendor = cls.env['lhi.vendor'].create({'name': 'Acc Vendor'})
        cls.po = cls.env['lhi.purchase.order'].create({
            'vendor_id': cls.vendor.id,
            'state': 'locked',
            'line_ids': [(0, 0, {'name': 'Item A', 'quantity': 1, 'price_unit': 100})]
        })
        
    def test_accounting_sync(self):
        self.po.action_send_to_accounting()
        self.assertEqual(self.po.accounting_status, 'transferred')
        
        sync = self.po.accounting_sync_id
        sync.process_accounting_update({
            'accepted': True,
            'bill_number': 'BILL/2030/001',
            'payment_status': 'paid'
        })
        
        self.assertEqual(self.po.accounting_status, 'accepted')
        self.assertEqual(self.po.bill_number, 'BILL/2030/001')
        self.assertEqual(self.po.payment_status, 'paid')
