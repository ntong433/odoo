from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestAssetManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.category = cls.env['lhi.asset.category'].create({'name': 'Computers', 'code': 'IT-COMP'})
        cls.user1 = cls.env.user
        cls.user2 = cls.env['res.users'].create({'name': 'User 2', 'login': 'user2'})
        
        cls.asset = cls.env['lhi.asset'].create({
            'name': 'Laptop Dell',
            'category_id': cls.category.id,
            'custodian_id': cls.user1.id,
        })
        cls.asset.action_activate()
        
    def test_asset_handover(self):
        self.assertEqual(self.asset.state, 'active')
        
        transfer = self.env['lhi.asset.transfer'].create({
            'asset_id': self.asset.id,
            'transfer_type': 'handover',
            'dest_custodian_id': self.user2.id,
            'justification': 'Reassignment'
        })
        
        transfer.action_submit()
        self.assertEqual(self.asset.state, 'transfer')
        
        transfer.action_approve()
        transfer.action_complete()
        
        self.assertEqual(self.asset.state, 'active')
        self.assertEqual(self.asset.custodian_id.id, self.user2.id)
        
    def test_asset_disposal(self):
        transfer = self.env['lhi.asset.transfer'].create({
            'asset_id': self.asset.id,
            'transfer_type': 'write_off',
            'justification': 'Broken beyond repair'
        })
        
        transfer.action_submit()
        transfer.action_approve()
        transfer.action_complete()
        
        self.assertEqual(self.asset.state, 'disposed')
        self.assertFalse(self.asset.custodian_id)
