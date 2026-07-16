from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestDocumentMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_local_purge_disabled(self):
        # By default, local purge is disabled via environment/config parameter
        self.env['ir.config_parameter'].sudo().set_param('DOCUMENT_LOCAL_PURGE_ENABLED', False)
        
        job = self.env['lhi.document.migration.job'].create({'name': 'Batch 1'})
        attachment = self.env['ir.attachment'].create({
            'name': 'test.pdf',
            'datas': 'dGVzdA=='
        })
        mapping = self.env['lhi.document.migration.mapping'].create({
            'job_id': job.id,
            'attachment_id': attachment.id,
            'classification': 'business',
            'state': 'verified'
        })
        
        with self.assertRaises(UserError):
            job.action_local_purge()
            
    def test_dry_run(self):
        job = self.env['lhi.document.migration.job'].create({'name': 'Batch 2', 'is_dry_run': True})
        attachment = self.env['ir.attachment'].create({
            'name': 'dryrun.pdf',
            'datas': 'dGVzdA=='
        })
        mapping = self.env['lhi.document.migration.mapping'].create({
            'job_id': job.id,
            'attachment_id': attachment.id,
            'classification': 'business'
        })
        
        job.action_run_migration()
        # Should only evaluate checksum and destination, not upload
        self.assertEqual(mapping.state, 'dry_run_ok')
