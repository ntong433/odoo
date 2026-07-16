from odoo.tests.common import TransactionCase

class TestPowerBI(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_powerbi_report_embed_url(self):
        report = self.env['lhi.powerbi.report'].create({
            'name': 'Executive Dashboard',
            'report_id': 'REP-999',
            'workspace_id': 'WS-888',
        })
        self.assertEqual(report.embed_url, 'https://app.powerbi.com/reportEmbed?reportId=REP-999&groupId=WS-888')
        
        action = report.action_view_report()
        self.assertEqual(action['tag'], 'lhi_powerbi.report_viewer')
        self.assertEqual(action['params']['report_id'], 'REP-999')
