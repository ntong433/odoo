from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestLhiMigrationTooling(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env['ir.config_parameter'].sudo().set_param('lhi_accounting_base.is_accounting_cutover_active', 'False')

    def test_migration_import_fails_when_disabled(self):
        tool = self.env['lhi.migration.tool'].create({
            'name': 'Import Vendors',
            'task_type': 'open_bills'
        })
        with self.assertRaises(UserError):
            tool.action_import()
