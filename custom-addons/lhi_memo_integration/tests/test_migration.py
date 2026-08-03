import hashlib
import importlib.util
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMemoIntegrationMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        department = cls.env["lhi.department"].create(
            {
                "name": "Memo Migration Test Department",
                "code": "MEMO-MIGRATION-TEST",
                "company_id": cls.company.id,
            }
        )
        category = cls.env["lhi.memo.category"].create(
            {
                "name": "Memo Migration Test Category",
                "code": "MEMO-MIGRATION-TEST",
                "company_id": cls.company.id,
            }
        )
        cls.memo = cls.env["lhi.memo"].create(
            {
                "title": "Historical failed Memo migration test",
                "subject": "Historical failed Memo migration test",
                "purpose": "Verify idempotent operation migration and document preservation.",
                "memo_category_id": category.id,
                "requester_id": cls.env.user.id,
                "department_id": department.id,
                "company_id": cls.company.id,
                "state": "failed",
                "integration_error_code": "historical_test_failure",
                "integration_error_message": "Safe historical test failure",
            }
        )

        connection = cls.env["lhi.graph.connection"].search(
            [("company_id", "=", cls.company.id), ("active", "=", True)],
            limit=1,
        )
        if not connection:
            connection = cls.env["lhi.graph.connection"].create(
                {
                    "name": "Memo Migration Test Graph",
                    "company_id": cls.company.id,
                    "tenant_id": "11111111-1111-4111-8111-111111111111",
                    "client_id": "22222222-2222-4222-8222-222222222222",
                }
            )
        policy = cls.env["lhi.document.storage.policy"].search(
            [
                ("model_name", "=", "lhi.memo"),
                ("field_name", "=", "source_docx_item_id"),
                ("company_id", "in", [False, cls.company.id]),
            ],
            limit=1,
        )
        if not policy:
            policy = cls.env["lhi.document.storage.policy"].create(
                {
                    "name": "Memo Migration Test Policy",
                    "model_name": "lhi.memo",
                    "field_name": "source_docx_item_id",
                    "company_id": cls.company.id,
                    "library_code": "operations",
                }
            )

        content = b"PK\x03\x04historical-memo-document"
        checksum = hashlib.sha256(content).hexdigest()
        cls.document_item = cls.env["lhi.document.item"].create(
            {
                "name": "historical-memo.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "file_size": len(content),
                "checksum": checksum,
                "sha1_checksum": hashlib.sha1(content).hexdigest(),
                "company_id": cls.company.id,
                "requested_by_id": cls.env.user.id,
                "graph_connection_id": connection.id,
                "storage_policy_id": policy.id,
                "linked_model": "lhi.memo",
                "linked_record_id": cls.memo.id,
                "linked_field": "source_docx_item_id",
                "linked_record_uuid": cls.memo.uuid,
                "storage_state": "available",
                "upload_state": "completed",
                "sharepoint_site_id": "migration-test-site",
                "sharepoint_drive_id": "migration-test-drive",
                "sharepoint_item_id": f"migration-test-item-{cls.memo.id}",
                "idempotency_key": cls.env["lhi.document.item"]._make_idempotency_key(
                    "lhi.memo",
                    cls.memo.id,
                    "source_docx_item_id",
                    "historical-memo.docx",
                    checksum,
                ),
            }
        )
        cls.memo.sudo().write({"source_docx_item_id": cls.document_item.id})

    def test_post_migration_is_idempotent_and_preserves_document_link(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "19.0.2.1.0"
            / "post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "lhi_memo_integration_post_migrate_19_0_2_1_0", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        migration.migrate(self.env.cr, "19.0.2.0.0")
        domain = [("correlation_id", "=", f"HISTORICAL-{self.memo.id}")]
        self.assertEqual(
            self.env["lhi.memo.integration.operation"].sudo().search_count(domain),
            1,
        )

        migration.migrate(self.env.cr, "19.0.2.0.0")
        self.assertEqual(
            self.env["lhi.memo.integration.operation"].sudo().search_count(domain),
            1,
        )
        self.memo.invalidate_recordset(["source_docx_item_id"])
        self.assertEqual(self.memo.sudo().source_docx_item_id, self.document_item)
