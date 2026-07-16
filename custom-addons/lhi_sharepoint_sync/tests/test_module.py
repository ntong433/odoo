from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestSharepointSync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_partition_safety_routing(self):
        partition = self.env['lhi.sharepoint.partition'].create({
            'name': 'Test Partition',
            'domain': 'Finance',
            'year': '2026',
            'project': 'PRJ-100',
            'site_id': 'site123',
            'drive_id': 'drive123',
            'root_folder_id': 'folder123',
            'item_count': 3999
        })
        
        # Should return successfully
        selected = self.env['lhi.sharepoint.partition'].select_partition('Finance', '2026', 'PRJ-100')
        self.assertEqual(selected.id, partition.id)
        
        # Increment to unsafe threshold
        partition.item_count = 4500
        partition._check_capacity()
        self.assertTrue(partition.read_only)
        
        # Should now fail to select this partition because it's read-only/unsafe
        with self.assertRaises(ValueError):
            self.env['lhi.sharepoint.partition'].select_partition('Finance', '2026', 'PRJ-100')
            
    def test_scoped_queries(self):
        partition = self.env['lhi.sharepoint.partition'].create({
            'name': 'Scoped',
            'site_id': 's', 'drive_id': 'd', 'root_folder_id': 'r'
        })
        self.env['lhi.document.metadata'].create({
            'name': 'Doc1',
            'drive_item_id': '1',
            'partition_id': partition.id,
            'project_code': 'PRJ-100'
        })
        self.env['lhi.document.metadata'].create({
            'name': 'Doc2',
            'drive_item_id': '2',
            'partition_id': partition.id,
            'project_code': 'PRJ-200'
        })
        
        docs = self.env['lhi.document.metadata'].get_scoped_documents(project_code='PRJ-100')
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].name, 'Doc1')
