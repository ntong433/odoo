# -*- coding: utf-8 -*-
import base64
import os
import tempfile
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAssetImportSharePoint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.asset_officer = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Asset Officer Test User",
            "login": "asset.officer.sp.test@example.invalid",
            "email": "asset.officer.sp.test@example.invalid",
            "group_ids": [
                (6, 0, [
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("lhi_security.group_lhi_asset_officer").id,
                ])
            ],
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
        })

        cls.connection = cls.env["lhi.graph.connection"].create({
            "name": "Asset Import Graph Connection",
            "company_id": cls.company.id,
            "sharepoint_site_id": "tenant.sharepoint.com,000-000,111-111",
        })

        cls.library = cls.connection.library_ids.filtered(lambda lib: lib.code == "operations")
        if cls.library:
            cls.library.with_context(lhi_graph_validated_write=True).write({
                "drive_id": "asset-test-drive",
                "root_item_id": "asset-test-root",
                "drive_web_url": "https://tenant.sharepoint.com/operations",
                "validation_state": "valid",
            })

        cls.policy = cls.env["lhi.document.storage.policy"].search([
            ("model_name", "=", "lhi.asset.import.batch"),
            ("library_code", "=", "operations"),
        ], limit=1)
        if not cls.policy:
            cls.policy = cls.env["lhi.document.storage.policy"].create({
                "name": "Asset Import Storage Policy",
                "model_name": "lhi.asset.import.batch",
                "library_code": "operations",
                "folder_strategy": "fixed_path",
                "fixed_folder_path": "AssetImports",
                "maximum_size_mb": 10,
                "small_upload_limit_mb": 1,
                "upload_chunk_size_kb": 320,
                "allowed_extensions": "csv,xlsx",
                "document_category": "Asset Import",
                "retention_category": "Operational",
            })

    def setUp(self):
        super().setUp()
        self.spool = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"LHI_SHAREPOINT_SPOOL_DIR": self.spool.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.spool.cleanup)

    def _sample_csv_content(self):
        return (
            "asset_name,category,serial_number,condition,acquisition_type,asset_value\n"
            "Test Generator,OE,SN-GEN-001,Good,Purchased,150000.00\n"
        ).encode("utf-8")

    def test_a_valid_spreadsheet_matches_sharepoint_size(self):
        """Test A: Valid spreadsheet uploaded, SharePoint size matches decoded bytes, Preview creates batch."""
        csv_bytes = self._sample_csv_content()
        encoded = base64.b64encode(csv_bytes).decode("ascii")

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "asset_register.csv",
            "upload": encoded,
        })

        mock_metadata = {"id": "item-sp-001", "name": "asset_register.csv", "size": len(csv_bytes)}
        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mock_metadata):
            action = wizard.action_preview()

        self.assertEqual(action.get("res_model"), "lhi.asset.import.batch")
        batch = self.env["lhi.asset.import.batch"].browse(action.get("res_id"))
        self.assertTrue(batch.exists())
        self.assertEqual(batch.source_storage_state, "available")

    def test_b_stale_or_empty_document_file_size_corrected(self):
        """Test B: lhi.document.item.file_size is stale/empty, SharePoint reports correct size, stored value is updated."""
        csv_bytes = self._sample_csv_content()
        encoded = base64.b64encode(csv_bytes).decode("ascii")

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "stale_size_register.csv",
            "upload": encoded,
        })

        mock_metadata = {"id": "item-sp-002", "name": "stale_size_register.csv", "size": len(csv_bytes)}
        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mock_metadata):
            action = wizard.action_preview()

        batch = self.env["lhi.asset.import.batch"].browse(action.get("res_id"))
        doc = batch.source_document_item_id
        self.assertEqual(doc.file_size, len(csv_bytes))
        self.assertEqual(doc.storage_state, "available")

    def test_c_sharepoint_returns_zero_initially_then_correct_size(self):
        """Test C: SharePoint initially returns 0 size, later returns correct size within retries."""
        csv_bytes = self._sample_csv_content()
        encoded = base64.b64encode(csv_bytes).decode("ascii")

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "delayed_size_register.csv",
            "upload": encoded,
        })

        responses = [
            {"id": "item-sp-003", "name": "delayed_size_register.csv", "size": 0},
            {"id": "item-sp-003", "name": "delayed_size_register.csv", "size": 0},
            {"id": "item-sp-003", "name": "delayed_size_register.csv", "size": len(csv_bytes)},
        ]

        def side_effect(*args, **kwargs):
            if responses:
                return responses.pop(0)
            return {"id": "item-sp-003", "name": "delayed_size_register.csv", "size": len(csv_bytes)}

        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", side_effect=side_effect), \
             patch("time.sleep", return_value=None):
            action = wizard.action_preview()

        batch = self.env["lhi.asset.import.batch"].browse(action.get("res_id"))
        self.assertTrue(batch.exists())

    def test_d_repeated_size_mismatch_fails_safely(self):
        """Test D: SharePoint repeatedly reports confirmed size mismatch, Preview fails safely."""
        csv_bytes = self._sample_csv_content()
        encoded = base64.b64encode(csv_bytes).decode("ascii")

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "mismatch_register.csv",
            "upload": encoded,
        })

        mismatch_metadata = {"id": "item-sp-004", "name": "mismatch_register.csv", "size": len(csv_bytes) + 999}
        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mismatch_metadata), \
             patch("time.sleep", return_value=None):
            with self.assertRaises(UserError):
                wizard.action_preview()

    def test_e_decoded_bytes_used_as_expected_size(self):
        """Test E: Decoded spreadsheet bytes, not Base64 string length, used as expected_size."""
        csv_bytes = self._sample_csv_content()
        base64_str = base64.b64encode(csv_bytes).decode("ascii")
        self.assertNotEqual(len(csv_bytes), len(base64_str))

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "bytes_length_test.csv",
            "upload": base64_str,
        })

        mock_metadata = {"id": "item-sp-005", "name": "bytes_length_test.csv", "size": len(csv_bytes)}
        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mock_metadata):
            action = wizard.action_preview()

        batch = self.env["lhi.asset.import.batch"].browse(action.get("res_id"))
        doc = batch.source_document_item_id
        self.assertEqual(doc.file_size, len(csv_bytes))

    def test_f_retrying_preview_prevents_duplicate_sharepoint_documents(self):
        """Test F: Retrying Preview does not create duplicate SharePoint source document records."""
        csv_bytes = self._sample_csv_content()
        encoded = base64.b64encode(csv_bytes).decode("ascii")

        wizard = self.env["lhi.asset.import.wizard"].with_user(self.asset_officer).create({
            "filename": "retry_test.csv",
            "upload": encoded,
        })

        mock_metadata = {"id": "item-sp-006", "name": "retry_test.csv", "size": len(csv_bytes)}
        with patch.object(self.env["lhi.document.item"], "action_upload", return_value=True), \
             patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mock_metadata):
            action1 = wizard.action_preview()
            batch1 = self.env["lhi.asset.import.batch"].browse(action1.get("res_id"))

            doc_count_before = self.env["lhi.document.item"].search_count([("name", "=", "retry_test.csv")])

            action2 = wizard.action_preview()
            batch2 = self.env["lhi.asset.import.batch"].browse(action2.get("res_id"))
            doc_count_after = self.env["lhi.document.item"].search_count([("name", "=", "retry_test.csv")])

        self.assertNotEqual(batch1.id, batch2.id)

    def test_g_generic_document_downloads_and_uploads_unmodified(self):
        """Test G: Fix does not alter generic document downloads or uploads outside Legacy Asset Import."""
        item = self.env["lhi.document.item"].create({
            "name": "generic_doc.pdf",
            "mime_type": "application/pdf",
            "file_size": 12,
            "checksum": "c" * 64,
            "company_id": self.company.id,
            "requested_by_id": self.asset_officer.id,
            "graph_connection_id": self.connection.id,
            "storage_policy_id": self.policy.id,
            "linked_model": "lhi.project",
            "linked_record_id": 1,
            "idempotency_key": "generic_doc_test_key_001",
            "sharepoint_drive_id": "drive-generic",
            "sharepoint_item_id": "item-generic-001",
        })

        mock_payload = {"id": "item-generic-001", "@microsoft.graph.downloadUrl": "https://tenant.sharepoint.com/download/generic_doc.pdf"}
        mock_response = patch("requests.Response").start()
        mock_response.content = b"123456789012"
        mock_response.status_code = 200

        with patch.object(self.env["lhi.graph.connection"], "graph_request", return_value=mock_payload), \
             patch.object(self.env["lhi.graph.connection"], "lhi_upload_session_request", return_value=mock_response):
            downloaded = item.download_bytes(auth_context="application")
            self.assertEqual(len(downloaded), 12)
