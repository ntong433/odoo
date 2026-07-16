import os
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestSignatureBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.vendor = cls.env['lhi.vendor'].create({'name': 'Sig Vendor'})
        cls.po = cls.env['lhi.purchase.order'].create({
            'vendor_id': cls.vendor.id,
            'line_ids': [(0, 0, {'name': 'Item A', 'quantity': 1, 'price_unit': 100})]
        })
        cls.po.action_submit()
        cls.po.action_approve()

        connection = cls.env['lhi.graph.connection'].search([
            ('company_id', '=', cls.env.company.id),
            ('active', '=', True),
        ], limit=1)
        if not connection:
            cls.env['lhi.graph.connection'].create({
                'name': 'Signature Test Graph',
                'company_id': cls.env.company.id,
                'sharepoint_site_id': (
                    'tenant.sharepoint.com,'
                    '00000000-0000-4000-8000-000000000001,'
                    '00000000-0000-4000-8000-000000000002'
                ),
            })

    def setUp(self):
        super().setUp()
        self.spool = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {'LHI_SHAREPOINT_SPOOL_DIR': self.spool.name}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.spool.cleanup)

    @staticmethod
    def _confirm_upload(documents):
        for document in documents:
            document.sudo().write({
                'sharepoint_site_id': 'site',
                'sharepoint_drive_id': 'drive',
                'sharepoint_item_id': f'item-{document.id}',
                'storage_state': 'available',
                'upload_state': 'completed',
            })
            document._remove_spool()
        return True
        
    def test_signature_locking(self):
        with patch.object(
            self.env.registry['lhi.document.item'],
            'action_upload',
            self._confirm_upload,
        ):
            # Cannot modify locked/signed PO commercial fields.
            self.po.action_send_for_signature()
            request = self.po.opensign_request_id
            self.assertEqual(self.po.signature_status, 'sent')
            self.assertTrue(self.po.is_locked)
            self.assertEqual(
                request.source_document_item_id.storage_state,
                'available',
            )
            self.assertFalse(request.source_pdf)

            with self.assertRaises(ValidationError):
                self.po.write({'amount_total': 500})

            # Cancel signature unlocks it.
            self.po.action_cancel_signature()
            self.assertFalse(self.po.is_locked)
            self.po.write({
                'line_ids': [(0, 0, {
                    'name': 'Item B',
                    'quantity': 2,
                    'price_unit': 50,
                })],
            })
            self.assertEqual(self.po.amount_total, 200)

            # A completed callback is accepted only after the signed PDF is
            # confirmed in SharePoint.
            self.po.action_send_for_signature()
            request = self.po.opensign_request_id
            request.process_callback(
                'completed',
                signed_pdf=b'%PDF-signed',
                signed_hash='hash',
            )

            self.assertEqual(
                request.signed_document_item_id.storage_state,
                'available',
            )
            self.assertFalse(request.signed_pdf)
            self.assertEqual(self.po.signature_status, 'signed')
            self.assertEqual(self.po.state, 'locked')
            self.assertTrue(self.po.is_locked)
