from odoo.tests.common import TransactionCase

class TestLhiWithholdingTax(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_wht_cert(self):
        partner = self.env['res.partner'].create({'name': 'Vendor'})
        cert = self.env['lhi.wht.certificate'].create({'vendor_id': partner.id})
        cert.action_approve()
        self.assertEqual(cert.state, 'approved')
