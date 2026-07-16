import os
import tempfile
from unittest.mock import Mock, patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSharePointStorage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["lhi.graph.connection"].create(
            {
                "name": "Storage Test Graph",
                "company_id": cls.env.company.id,
                "sharepoint_site_id": (
                    "tenant.sharepoint.com,"
                    "00000000-0000-4000-8000-000000000001,"
                    "00000000-0000-4000-8000-000000000002"
                ),
            }
        )
        cls.library = cls.connection.library_ids.filtered(
            lambda library: library.code == "operations"
        )
        cls.library.with_context(lhi_graph_validated_write=True).write(
            {
                "drive_id": "test-drive",
                "root_item_id": "test-root",
                "drive_web_url": "https://tenant.sharepoint.com/operations",
                "validation_state": "valid",
            }
        )
        cls.policy = cls.env["lhi.document.storage.policy"].create(
            {
                "name": "Project Test Documents",
                "model_name": "lhi.activity",
                "library_code": "operations",
                "folder_strategy": "model_record",
                "maximum_size_mb": 10,
                "small_upload_limit_mb": 1,
                "upload_chunk_size_kb": 320,
                "allowed_extensions": "pdf,txt",
                "document_category": "Operations",
                "retention_category": "Operational",
            }
        )
        cls.project = cls.env["lhi.project"].create(
            {"name": "Storage Test Project", "code": "SP-STORAGE-TEST"}
        )
        cls.business_record = cls.env["lhi.activity"].create(
            {
                "name": "SharePoint Storage Test Record",
                "code": "SP-STORAGE-ACTIVITY",
                "project_id": cls.project.id,
            }
        )
        cls.internal_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "SharePoint Ordinary User",
                "login": "sharepoint.storage.user@example.invalid",
                "email": "sharepoint.storage.user@example.invalid",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                "company_id": cls.env.company.id,
                "company_ids": [(6, 0, [cls.env.company.id])],
            }
        )

    def setUp(self):
        super().setUp()
        self.spool = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"LHI_SHAREPOINT_SPOOL_DIR": self.spool.name}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.spool.cleanup)

    def _new_item(self, **extra):
        values = {
            "name": "test.pdf",
            "mime_type": "application/pdf",
            "file_size": 10,
            "checksum": "a" * 64,
            "sha1_checksum": "b" * 40,
            "company_id": self.env.company.id,
            "requested_by_id": self.env.user.id,
            "graph_connection_id": self.connection.id,
            "storage_policy_id": self.policy.id,
            "linked_model": self.business_record._name,
            "linked_record_id": self.business_record.id,
            "linked_record_uuid": f"lhi.activity:{self.business_record.id}",
            "idempotency_key": self.env["ir.sequence"].next_by_code(
                "lhi.project"
            )
            or os.urandom(16).hex(),
        }
        values.update(extra)
        return self.env["lhi.document.item"].sudo().create(values)

    def test_policy_rejects_unapproved_extension_and_invalid_chunk(self):
        with self.assertRaises(ValidationError):
            self.policy.validate_file("payload.exe", 100)
        with self.assertRaises(ValidationError):
            self.policy.copy({"upload_chunk_size_kb": 321})

    def test_technical_attachment_remains_on_standard_storage(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "technical.txt",
                "raw": b"technical bytes",
                "mimetype": "text/plain",
                "res_model": "res.users",
                "res_id": self.env.user.id,
            }
        )
        self.assertFalse(attachment.lhi_document_item_id)
        self.assertEqual(attachment.raw, b"technical bytes")

    def test_failed_business_upload_is_spooled_and_not_left_in_filestore(self):
        def fail_upload(records):
            raise UserError("SharePoint unavailable")

        with patch.object(
            self.env.registry["lhi.document.item"], "action_upload", fail_upload
        ):
            attachment = self.env["ir.attachment"].create(
                {
                    "name": "evidence.pdf",
                    "raw": b"%PDF-test-business-document",
                    "mimetype": "application/pdf",
                    "res_model": self.business_record._name,
                    "res_id": self.business_record.id,
                }
            )
        document = attachment.lhi_document_item_id
        self.assertTrue(document)
        self.assertEqual(document.storage_state, "failed")
        self.assertFalse(attachment.store_fname)
        self.assertFalse(attachment.db_datas)
        self.assertTrue(os.path.isfile(document.sudo().spool_path))
        self.assertTrue(
            self.env["lhi.integration.job"].search(
                [
                    ("model_name", "=", "lhi.document.item"),
                    ("record_id", "=", document.id),
                    ("action", "=", "upload"),
                ]
            )
        )

    def test_confirmed_business_upload_removes_temporary_bytes(self):
        def complete_upload(records):
            for document in records:
                document.sudo().write(
                    {
                        "sharepoint_site_id": "site",
                        "sharepoint_drive_id": "drive",
                        "sharepoint_item_id": f"item-{document.id}",
                        "storage_state": "available",
                        "upload_state": "completed",
                    }
                )
                document._remove_spool()
            return True

        with patch.object(
            self.env.registry["lhi.document.item"], "action_upload", complete_upload
        ):
            attachment = self.env["ir.attachment"].create(
                {
                    "name": "confirmed.pdf",
                    "raw": b"%PDF-confirmed",
                    "mimetype": "application/pdf",
                    "res_model": self.business_record._name,
                    "res_id": self.business_record.id,
                }
            )
        self.assertEqual(attachment.lhi_storage_state, "available")
        self.assertFalse(attachment.store_fname)
        self.assertFalse(attachment.db_datas)
        self.assertFalse(attachment.lhi_document_item_id.sudo().spool_path)

    def test_large_upload_resumes_from_last_confirmed_offset(self):
        content = b"x" * (640 * 1024)
        item = self._new_item(
            name="large.pdf",
            file_size=len(content),
            checksum="c" * 64,
        )
        accepted = Mock(status_code=202)
        accepted.json.return_value = {"nextExpectedRanges": ["327680-"]}
        completed = Mock(status_code=201)
        completed.json.return_value = {
            "id": "completed-item",
            "size": len(content),
        }
        session = {
            "uploadUrl": "https://upload.files.1drv.com/session-token",
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }
        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "lhi_create_upload_session",
            return_value=session,
        ) as create_session, patch.object(
            self.env.registry["lhi.graph.connection"],
            "lhi_upload_session_request",
            side_effect=[accepted, UserError("connection interrupted")],
        ) as upload_request:
            try:
                item._upload_large(self.library, "parent", content)
            except UserError:
                pass
            else:
                self.fail("The simulated upload interruption was not raised.")
        self.assertEqual(upload_request.call_count, 2)
        accepted.json.assert_called_once()
        item.invalidate_recordset(["upload_next_offset", "upload_url"])
        self.assertEqual(item.upload_next_offset, 327680)
        create_session.assert_called_once()

        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "lhi_create_upload_session",
        ) as create_session, patch.object(
            self.env.registry["lhi.graph.connection"],
            "lhi_upload_session_request",
            return_value=completed,
        ):
            payload = item._upload_large(self.library, "parent", content)
        self.assertEqual(payload["id"], "completed-item")
        create_session.assert_not_called()

    def test_document_metadata_is_not_available_to_ordinary_users(self):
        item = self._new_item()
        with self.assertRaises(AccessError):
            item.with_user(self.internal_user).check_access("read")

    def test_queue_creation_is_idempotent(self):
        item = self._new_item()
        first = item._enqueue("upload")
        second = item._enqueue("upload")
        self.assertEqual(first, second)

    def test_sharepoint_metadata_uses_provisioned_columns(self):
        item = self._new_item(
            document_category="Asset",
            workflow_state="approved",
            retention_category="Operational",
        )
        with patch.object(
            self.env.registry["lhi.graph.connection"], "graph_request", return_value={}
        ) as request_mock:
            item.sudo().write(
                {
                    "sharepoint_drive_id": "drive",
                    "sharepoint_item_id": "item",
                }
            )
            item._patch_sharepoint_metadata()
        metadata = request_mock.call_args.kwargs["json_body"]
        self.assertEqual(metadata["LhiDocumentClass"], "Operations")
        self.assertEqual(metadata["LhiOdooRecordId"], self.business_record.id)
        self.assertIn("LhiContentSha256", metadata)
        self.assertNotIn("LhiConfidentiality", metadata)
