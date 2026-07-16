from odoo.tests.common import TransactionCase

class TestLhiFieldCash(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_field_cashbook(self):
        cashbook = self.env['lhi.field.cashbook'].create({
            'name': 'Abuja Cashbook',
            'custodian_id': self.env.user.id
        })
        cashbook.action_start_reconciliation()
        self.assertEqual(cashbook.state, 'reconciling')
