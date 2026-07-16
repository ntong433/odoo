from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError

class TestRBACSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.user_auditor = cls.env['res.users'].create({
            'name': 'Auditor',
            'login': 'auditor@lhinigeria.org',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])]
        })
        
    def test_auditor_read_only(self):
        # We ensure auditor cannot write to proposals
        proposal = self.env['lhi.proposal'].create({
            'name': 'Audit Proposal'
        })
        
        with self.assertRaises(AccessError):
            proposal.with_user(self.user_auditor).write({'name': 'Hacked'})
