from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestLhiNgHrPayroll(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')

    def test_payslip_post_fails_when_disabled(self):
        emp = self.env['hr.employee'].create({'name': 'Jane Doe'})
        struct = self.env['lhi.payroll.structure'].create({'name': 'Standard', 'date_start': '2026-01-01'})
        slip = self.env['lhi.payslip'].create({
            'employee_id': emp.id,
            'structure_id': struct.id,
            'date_from': '2026-07-01',
            'date_to': '2026-07-31'
        })
        with self.assertRaises(UserError):
            slip.action_post_journals()
