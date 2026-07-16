from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestPurchaseOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.vendor = cls.env['lhi.vendor'].create({'name': 'PO Vendor'})
        cls.po = cls.env['lhi.purchase.order'].create({
            'vendor_id': cls.vendor.id,
            'line_ids': [
                (0, 0, {'name': 'Item A', 'quantity': 10, 'price_unit': 100})
            ]
        })
        
    def test_po_lifecycle(self):
        self.assertEqual(self.po.amount_total, 1000)
        
        self.po.action_submit()
        self.assertEqual(self.po.state, 'to_approve')
        
        self.po.action_approve()
        self.assertEqual(self.po.state, 'approved')
        
        # Receipt validation
        receipt = self.env['lhi.receipt'].create({
            'order_id': self.po.id,
            'receipt_type': 'goods',
            'line_ids': [
                (0, 0, {
                    'order_line_id': self.po.line_ids[0].id,
                    'qty_received': 10
                })
            ]
        })
        receipt.action_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(self.po.line_ids[0].qty_received, 10)
        
        # Over-receipt should fail
        receipt2 = self.env['lhi.receipt'].create({
            'order_id': self.po.id,
            'receipt_type': 'goods',
            'line_ids': [
                (0, 0, {
                    'order_line_id': self.po.line_ids[0].id,
                    'qty_received': 5
                })
            ]
        })
        with self.assertRaises(ValidationError):
            receipt2.action_validate()
