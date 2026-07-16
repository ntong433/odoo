from odoo.tests.common import TransactionCase

class TestLhiMultiCurrency(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_donor_currency_fields(self):
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'lhi_rate_source': 'cbn'
        })
        self.assertEqual(move.lhi_rate_source, 'cbn')
