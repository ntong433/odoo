from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestLhiGrantAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_donor_restriction(self):
        with self.assertRaises(ValidationError):
            self.env['account.analytic.account'].create({
                'name': 'Restricted Grant',
                'lhi_restriction_type': 'temporarily_restricted'
            })
