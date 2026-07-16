from odoo.tests.common import TransactionCase

class TestLeaveBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.user = cls.env.user
        cls.user.write({'lhi_entra_object_id': 'ENTRA-12345'})
        
    def test_leave_cache(self):
        cache = self.env['lhi.leave.cache'].create({
            'user_id': self.user.id,
            'annual_balance': 15.0,
            'sick_balance': 5.0,
        })
        self.assertEqual(cache.entra_object_id, 'ENTRA-12345')
        
    def test_unified_inbox(self):
        inbox = self.env['lhi.unified.inbox'].create({
            'name': 'Test Inbox Item',
            'approver_id': self.user.id,
            'source_system': 'leave',
            'external_reference': 'REQ-777',
            'action_url': 'https://leave.lhinigeria.org/req/777'
        })
        self.assertEqual(inbox.status, 'pending')
