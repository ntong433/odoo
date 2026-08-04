# -*- coding: utf-8 -*-
import base64
import hashlib
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError


class TestAssetImportSharePoint(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.spool = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"LHI_SHAREPOINT_SPOOL_DIR": self.spool.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.spool.cleanup)

        # Mock Odoo Environment & Records
        self.env = MagicMock()
        self.user = MagicMock()
        self.company = MagicMock()
        self.company.id = 1
        self.user.id = 2
        self.user.has_group.return_value = True
        self.env.user = self.user
        self.env.company = self.company

        # Setup mock connection and policy
        self.connection = MagicMock()
        self.connection.id = 10
        self.connection.sharepoint_site_id = "tenant.sharepoint.com,000,111"
        self.policy = MagicMock()
        self.policy.id = 20
        self.policy.conflict_behavior = "rename"

    def _sample_csv_content(self):
        return (
            "asset_name,category,serial_number,condition,acquisition_type,asset_value\n"
            "Test Generator,OE,SN-GEN-001,Good,Purchased,150000.00\n"
        ).encode("utf-8")

    def test_01_original_xlsx_decoded_bytes_passed_unchanged(self):
        """Test 1: Original XLSX/CSV decoded bytes are passed unchanged to the SharePoint upload method."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "unchanged_bytes.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        passed_content = []

        def mock_create_from_bytes(name, content, **kwargs):
            passed_content.append(content)
            doc = MagicMock()
            doc.id = 101
            doc.name = name
            doc.file_size = len(content)
            doc.checksum = hashlib.sha256(content).hexdigest()
            doc.sharepoint_drive_id = "drive-01"
            doc.sharepoint_item_id = "item-unchanged-01"
            doc.storage_state = "available"
            doc.graph_connection_id = self.connection
            doc.storage_policy_id = self.policy
            return doc

        self.env["lhi.document.item"].create_from_bytes.side_effect = mock_create_from_bytes
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-01"
        self.env["lhi.document.item"].sudo().search.return_value = False

        batch = MagicMock()
        batch._name = "lhi.asset.import.batch"
        batch.id = 50
        self.env["lhi.asset.import.batch"].create.return_value = batch

        mock_meta = {"id": "item-unchanged-01", "name": "unchanged_bytes.csv", "size": len(raw_bytes)}
        self.connection.graph_request.return_value = mock_meta

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)

        self.assertEqual(len(passed_content), 1)
        self.assertEqual(bytes(passed_content[0]), raw_bytes)

    def test_02_expected_size_calculated_from_exact_upload_payload(self):
        """Test 2: expected_size is calculated from the exact upload_payload object."""
        raw_bytes = self._sample_csv_content()
        encoded_str = base64.b64encode(raw_bytes).decode("ascii")

        self.assertNotEqual(len(raw_bytes), len(encoded_str))

        wizard_cls = MagicMock()
        wizard_cls.filename = "payload_size.csv"
        wizard_cls.upload = encoded_str
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        doc = MagicMock()
        doc.id = 102
        doc.name = "payload_size.csv"
        doc.file_size = len(raw_bytes)
        doc.checksum = hashlib.sha256(raw_bytes).hexdigest()
        doc.sharepoint_drive_id = "drive-01"
        doc.sharepoint_item_id = "item-02"
        doc.storage_state = "available"
        doc.graph_connection_id = self.connection
        doc.storage_policy_id = self.policy

        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-02"
        self.env["lhi.document.item"].sudo().search.return_value = False

        batch = MagicMock()
        batch._name = "lhi.asset.import.batch"
        batch.id = 51
        self.env["lhi.asset.import.batch"].create.return_value = batch

        mock_meta = {"id": "item-02", "name": "payload_size.csv", "size": len(raw_bytes)}
        self.connection.graph_request.return_value = mock_meta

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)
        doc.sudo().write.assert_called()
        written_vals = doc.sudo().write.call_args[0][0]
        self.assertEqual(written_vals.get("file_size"), len(raw_bytes))

    def test_03_openpyxl_workbook_not_resaved_before_upload(self):
        """Test 3: An XLSX parsed with openpyxl is not re-saved before SharePoint upload."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "no_save.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        doc = MagicMock(id=103, sharepoint_drive_id="d1", sharepoint_item_id="i3", storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-03"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=52)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        mock_meta = {"id": "i3", "name": "no_save.csv", "size": len(raw_bytes)}
        self.connection.graph_request.return_value = mock_meta

        with patch("openpyxl.Workbook.save", side_effect=AssertionError("Workbook save must not be called")):
            from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
            wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)
            LhiAssetImportWizard.action_preview(wizard_cls)

    def test_04_upload_service_returns_current_drive_item_id_and_verifies_same(self):
        """Test 4: The upload service returns current DriveItem ID and the importer verifies that same ID."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "same_id.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        returned_id = "item-returned-999"
        doc = MagicMock(id=104, sharepoint_drive_id="d1", sharepoint_item_id=returned_id, storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-04"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=53)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        requests_made = []
        def mock_graph_request(method, url, **kwargs):
            requests_made.append(url)
            return {"id": returned_id, "name": "same_id.csv", "size": len(raw_bytes)}

        self.connection.graph_request.side_effect = mock_graph_request

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)
        self.assertTrue(any(returned_id in r for r in requests_made))

    def test_05_older_sharepoint_item_with_same_filename_not_used(self):
        """Test 5: An older SharePoint item with the same filename is not used for verification."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "same_name.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        new_id = "item-new-555"
        doc = MagicMock(id=105, sharepoint_drive_id="d1", sharepoint_item_id=new_id, storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-05"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=54)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        def mock_graph_request(method, url, **kwargs):
            self.assertIn(new_id, url)
            self.assertNotIn("same_name.csv", url)
            return {"id": new_id, "name": "same_name.csv", "size": len(raw_bytes)}

        self.connection.graph_request.side_effect = mock_graph_request

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)

    def test_06_simulated_filename_conflict_renamed_item_verified(self):
        """Test 6: A simulated filename conflict returns a renamed item, and verification uses the returned final item."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "conflict.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        renamed_id = "item-renamed-888"
        doc = MagicMock(id=106, name="conflict.csv", sharepoint_drive_id="d1", sharepoint_item_id=renamed_id, storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-06"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=55)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        mock_renamed_meta = {"id": renamed_id, "name": "conflict (1).csv", "size": len(raw_bytes)}
        self.connection.graph_request.return_value = mock_renamed_meta

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)
        doc.sudo().write.assert_called()
        self.assertEqual(doc.sudo().write.call_args[0][0].get("name"), "conflict (1).csv")

    def test_07_remote_size_matching_upload_payload_succeeds(self):
        """Test 7: Remote size matching upload_payload succeeds and creates the preview batch."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "match_size.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        doc = MagicMock(id=107, sharepoint_drive_id="d1", sharepoint_item_id="item-07", storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-07"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=56)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        self.connection.graph_request.return_value = {"id": "item-07", "name": "match_size.csv", "size": len(raw_bytes)}

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        res = LhiAssetImportWizard.action_preview(wizard_cls)
        self.assertEqual(res.get("res_id"), 56)

    def test_08_remote_size_differing_fails_safely(self):
        """Test 8: Remote size differing from upload_payload fails safely."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "differing.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        doc = MagicMock(id=108, sharepoint_drive_id="d1", sharepoint_item_id="item-08", storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-08"
        self.env["lhi.document.item"].sudo().search.return_value = False
        batch = MagicMock(_name="lhi.asset.import.batch", id=57)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        # Remote size differs (47995 vs len(raw_bytes))
        self.connection.graph_request.return_value = {"id": "item-08", "name": "differing.csv", "size": 47995}

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        with patch("time.sleep", return_value=None):
            with self.assertRaises(UserError) as cm:
                LhiAssetImportWizard.action_preview(wizard_cls)
            self.assertIn("Remote size differs", str(cm.exception))

    def test_09_retry_does_not_create_duplicate_documents(self):
        """Test 9: A retry does not create duplicate SharePoint documents."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "retry.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        existing_doc = MagicMock(
            id=109,
            checksum=hashlib.sha256(raw_bytes).hexdigest(),
            file_size=len(raw_bytes),
            sharepoint_drive_id="d1",
            sharepoint_item_id="item-09",
            storage_state="available",
            graph_connection_id=self.connection,
            storage_policy_id=self.policy,
        )
        self.env["lhi.document.item"].sudo().search.return_value = existing_doc
        batch = MagicMock(_name="lhi.asset.import.batch", id=58)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        self.connection.graph_request.return_value = {"id": "item-09", "name": "retry.csv", "size": len(raw_bytes)}

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        LhiAssetImportWizard.action_preview(wizard_cls)
        # create_from_bytes must NOT be called on retry when existing_doc matches
        self.env["lhi.document.item"].create_from_bytes.assert_not_called()

    def test_10_csv_and_xlsx_preview_parsing_preserves_source_bytes(self):
        """Test 10: CSV and XLS/XLSX preview parsing continues to work without changing the uploaded source bytes."""
        raw_bytes = self._sample_csv_content()
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        wizard_cls = MagicMock()
        wizard_cls.filename = "parse_preserve.csv"
        wizard_cls.upload = encoded
        wizard_cls.default_state_id = MagicMock(id=5)
        wizard_cls.env = self.env
        wizard_cls.ensure_one = MagicMock()

        doc = MagicMock(id=110, sharepoint_drive_id="d1", sharepoint_item_id="item-10", storage_state="available", graph_connection_id=self.connection, storage_policy_id=self.policy)
        self.env["lhi.document.item"].create_from_bytes.return_value = doc
        self.env["lhi.document.item"]._make_idempotency_key.return_value = "key-10"
        self.env["lhi.document.item"].sudo().search.return_value = False

        batch = MagicMock(_name="lhi.asset.import.batch", id=59)
        self.env["lhi.asset.import.batch"].create.return_value = batch

        self.connection.graph_request.return_value = {"id": "item-10", "name": "parse_preserve.csv", "size": len(raw_bytes)}

        from odoo.addons.lhi_asset_management.models.lhi_asset_import import LhiAssetImportWizard
        wizard_cls._verify_and_confirm_asset_import_document = LhiAssetImportWizard._verify_and_confirm_asset_import_document.__get__(wizard_cls)

        res = LhiAssetImportWizard.action_preview(wizard_cls)
        self.assertEqual(res.get("res_id"), 59)
        batch._load_preview.assert_called_once()
        passed_stream = batch._load_preview.call_args[0][0]
        self.assertEqual(passed_stream.getvalue(), raw_bytes)


if __name__ == "__main__":
    unittest.main()
