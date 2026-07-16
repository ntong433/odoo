from odoo.tests.common import TransactionCase

class TestReportingHub(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_reporting_job(self):
        job = self.env['lhi.reporting.job'].create({
            'name': 'Test Donor Sync',
            'target_table': 'dim_donor',
            'extraction_query': 'SELECT * FROM res_partner WHERE is_company=True'
        })
        self.assertEqual(job.status, 'idle')
        job.action_run_sync()
        self.assertEqual(job.status, 'success')
        self.assertEqual(job.records_synced, 100)
        
    def test_quality_check(self):
        job = self.env['lhi.reporting.job'].create({
            'name': 'Test Sync',
            'target_table': 'fact_budget',
        })
        check = self.env['lhi.data.quality.check'].create({
            'name': 'No negative budget',
            'job_id': job.id,
            'check_query': 'SELECT COUNT(*) FROM fact_budget WHERE amount < 0',
            'expected_result': '0'
        })
        check.action_evaluate()
        self.assertTrue(check.is_passing)
