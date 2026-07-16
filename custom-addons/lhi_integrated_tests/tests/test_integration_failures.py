from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestIntegrationFailures(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_accounting_sync_failure_handling(self):
        # Dormant accounting gate must block standard financial syncing
        self.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')
        
        gate = self.env['lhi.accounting.feature.gate']
        with self.assertRaises(UserError):
            gate.check_accounting_enabled()
