from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestLhiAdvanceAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')

    def test_advance(self):
        emp = self.env['hr.employee'].create({'name': 'John'})
        adv = self.env['lhi.staff.advance'].create({
            'employee_id': emp.id,
            'amount': 500
        })
        adv.action_approve()
        
        # Payment should fail because gate is closed
        with self.assertRaises(UserError):
            adv.action_register_payment()
