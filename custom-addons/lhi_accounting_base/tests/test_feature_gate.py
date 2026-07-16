from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestAccountingFeatureGate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Ensure gate is closed
        cls.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')
        
    def test_gate_blocks_posting(self):
        # We simulate posting
        with self.assertRaises(UserError):
            self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
            
    def test_gate_allows_when_active(self):
        self.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'True')
        result = self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.assertTrue(result)
