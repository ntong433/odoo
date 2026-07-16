from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestLhiNgEdi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')

    def test_submit_edi_fails_when_disabled(self):
        move = self.env['account.move'].create({'move_type': 'out_invoice'})
        edi = self.env['lhi.ng.edi.adapter'].create({
            'name': 'INV-001-EDI',
            'move_id': move.id,
            'idempotency_key': 'abc-123'
        })
        with self.assertRaises(UserError):
            edi.action_submit()
