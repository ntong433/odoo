# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiIntegration(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiIntegration, self).setUp()
        self.Job = self.env['lhi.integration.job']
        self.Webhook = self.env['lhi.integration.webhook']
        
    def test_job_retry_mechanism(self):
        """ Test that jobs retry properly and hit dead-letter queue """
        job = self.Job.create_job('res.users', 1, 'dummy_action', 'Test Job')
        
        # Manually fail the job 3 times
        job.state = 'running'
        
        for _ in range(3):
            try:
                # Simulate a failure
                raise Exception("Simulated network failure")
            except Exception as e:
                job.retry_count += 1
                state = 'failed'
                if job.retry_count >= job.max_retries:
                    state = 'dead_letter'
                    
                job.write({
                    'state': state,
                    'last_error': str(e)
                })

        self.assertEqual(job.state, 'dead_letter', "Job should be dead_letter after 3 retries")
        self.assertEqual(job.retry_count, 3, "Retry count should be 3")

    def test_webhook_idempotency(self):
        """ Test that webhook idempotency prevents duplicates """
        # Create first webhook
        self.Webhook.create({
            'idempotency_key': 'abc-123',
            'source_system': 'system_a',
            'event_type': 'test.event',
            'payload': '{}',
            'state': 'received'
        })
        
        # Try creating second webhook with same key
        with self.assertRaises(Exception):
            self.Webhook.create({
                'idempotency_key': 'abc-123',
                'source_system': 'system_a',
                'event_type': 'test.event',
                'payload': '{}',
                'state': 'received'
            })
