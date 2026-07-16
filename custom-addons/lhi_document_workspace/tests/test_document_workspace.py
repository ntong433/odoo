from unittest.mock import patch
from types import SimpleNamespace

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLhiDocumentWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["lhi.graph.connection"].create(
            {
                "name": "Workspace Graph Test",
                "company_id": cls.env.company.id,
                "sharepoint_site_id": (
                    "tenant.sharepoint.com,"
                    "00000000-0000-4000-8000-000000000001,"
                    "00000000-0000-4000-8000-000000000002"
                ),
            }
        )
        cls.project = cls.env["lhi.project"].create(
            {"name": "Workspace Project", "code": "WORKSPACE-TEST"}
        )
        cls.other_project = cls.env["lhi.project"].create(
            {"name": "Other Workspace Project", "code": "WORKSPACE-OTHER"}
        )
        cls.closeout = cls.env["lhi.project.closeout"].create(
            {
                "name": "Locked Closeout",
                "project_id": cls.project.id,
                "state": "completed",
            }
        )
        cls.read_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Workspace Read User",
                "login": "workspace.read@example.invalid",
                "email": "workspace.read@example.invalid",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set(cls.env.company.ids)],
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.edit_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Workspace Edit User",
                "login": "workspace.edit@example.invalid",
                "email": "workspace.edit@example.invalid",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set(cls.env.company.ids)],
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("lhi_security.group_lhi_manager").id,
                        ]
                    )
                ],
            }
        )
        cls.project_policy = cls.env.ref(
            "lhi_sharepoint_storage.policy_projects"
        )
        cls.closeout_policy = cls.env.ref(
            "lhi_sharepoint_storage.policy_project_closeout"
        )
        cls.project_library = cls.connection.library_ids.filtered(
            lambda library: library.code == "projects"
        )
        cls.project_library.with_context(lhi_graph_validated_write=True).write(
            {
                "drive_id": "project-drive",
                "root_item_id": "project-root",
                "drive_web_url": "https://tenant.sharepoint.com/projects",
                "validation_state": "valid",
            }
        )

    def _document(self, record=None, policy=None, **extra):
        record = record or self.project
        policy = policy or self.project_policy
        values = {
            "name": "workspace-test.docx",
            "mime_type": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            "file_size": 128,
            "checksum": "a" * 64,
            "sha1_checksum": "b" * 40,
            "company_id": self.env.company.id,
            "requested_by_id": self.edit_user.id,
            "graph_connection_id": self.connection.id,
            "storage_policy_id": policy.id,
            "sharepoint_site_id": "site-id",
            "sharepoint_drive_id": "drive-id",
            "sharepoint_item_id": f"item-{record._name}-{record.id}",
            "sharepoint_parent_item_id": "parent-id",
            "sharepoint_web_url": (
                "https://tenant.sharepoint.com/sites/LHIERP/workspace-test.docx"
            ),
            "sharepoint_etag": '"etag-1"',
            "sharepoint_version": '"version-1"',
            "linked_model": record._name,
            "linked_record_id": record.id,
            "linked_record_uuid": f"{record._name}:{record.id}",
            "project_id": (
                record.id
                if record._name == "lhi.project"
                else getattr(record, "project_id", self.env["lhi.project"]).id
            ),
            "document_category": policy.document_category,
            "confidentiality": policy.confidentiality,
            "workflow_state": (
                str(record.state)
                if "state" in record._fields and record.state
                else False
            ),
            "retention_category": policy.retention_category,
            "storage_state": "available",
            "upload_state": "completed",
            "reconciliation_state": "matched",
            "idempotency_key": (
                f"workspace-test:{record._name}:{record.id}:{extra.get('name', '')}"
            ),
        }
        values.update(extra)
        return self.env["lhi.document.item"].sudo().create(values)

    @staticmethod
    def _remote_payload(document, etag='"etag-2"'):
        return {
            "id": document.sharepoint_item_id,
            "name": document.name,
            "size": document.file_size,
            "eTag": etag,
            "cTag": '"version-2"',
            "webUrl": (
                "https://tenant.sharepoint.com/sites/LHIERP/workspace-test.docx"
                "?source=odoo"
            ),
            "lastModifiedDateTime": "2026-07-16T10:00:00Z",
            "lastModifiedBy": {"user": {"displayName": "Entra User"}},
            "parentReference": {
                "driveId": document.sharepoint_drive_id,
                "id": document.sharepoint_parent_item_id,
            },
            "file": {"mimeType": document.mime_type, "hashes": {}},
        }

    def test_workspace_is_bounded_to_record_or_project(self):
        visible = self._document()
        hidden = self._document(
            record=self.other_project,
            name="other-project.docx",
            sharepoint_item_id="other-project-item",
        )
        result = self.project.with_user(self.read_user).lhi_workspace_get(
            scope="project", limit=100
        )
        uuids = {value["uuid"] for value in result["documents"]}
        self.assertIn(visible.uuid, uuids)
        self.assertNotIn(hidden.uuid, uuids)
        self.assertTrue(result["project_scope_available"])

    def test_readonly_user_can_preview_but_cannot_edit(self):
        document = self._document()
        result = self.project.with_user(self.read_user).lhi_workspace_get()
        value = next(
            item for item in result["documents"] if item["uuid"] == document.uuid
        )
        self.assertTrue(value["can_preview"])
        self.assertFalse(value["can_edit"])
        with self.assertRaises(AccessError):
            self.project.with_user(self.read_user).lhi_workspace_action(
                document.uuid, "edit"
            )

    def test_edit_uses_delegated_graph_and_browser_mode(self):
        document = self._document()
        calls = []

        def graph_request(connection, method, resource, **kwargs):
            calls.append((method, resource, kwargs))
            return self._remote_payload(document)

        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_request",
            graph_request,
        ):
            result = self.project.with_user(self.edit_user).lhi_workspace_action(
                document.uuid, "edit"
            )
        self.assertIn("web=1", result["url"])
        self.assertEqual(calls[0][2]["auth_context"], "delegated")
        self.assertEqual(calls[0][2]["user"], self.edit_user)
        self.assertTrue(
            self.env["lhi.audit.log"].sudo().search_count(
                [
                    ("event_type", "=", "document_edit"),
                    ("user_id", "=", self.edit_user.id),
                    ("res_model", "=", "lhi.project"),
                    ("res_id", "=", self.project.id),
                ]
            )
        )

    def test_workflow_locked_document_denies_mutation(self):
        document = self._document(
            record=self.closeout,
            policy=self.closeout_policy,
            project_id=self.project.id,
            sharepoint_item_id="locked-closeout-item",
        )
        value = self.closeout.with_user(self.read_user).lhi_workspace_get()[
            "documents"
        ][0]
        self.assertTrue(value["locked"])
        self.assertFalse(value["can_write"])
        with self.assertRaises(AccessError):
            self.closeout.with_user(self.read_user).lhi_workspace_action(
                document.uuid, "replace"
            )

    def test_preview_rejects_unsafe_url_and_uses_delegated_identity(self):
        document = self._document()

        def safe_preview(connection, method, resource, **kwargs):
            self.assertEqual(kwargs["auth_context"], "delegated")
            self.assertEqual(kwargs["user"], self.read_user)
            return {"getUrl": "https://tenant.sharepoint.com/preview/short-lived"}

        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_request",
            safe_preview,
        ):
            payload = document.with_context(
                lhi_workspace_user_id=self.read_user.id
            )._workspace_preview_payload(self.read_user)
        self.assertTrue(payload["getUrl"].startswith("https://"))

        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_request",
            return_value={"getUrl": "javascript:alert(1)"},
        ):
            with self.assertRaises(UserError):
                document.with_context(
                    lhi_workspace_user_id=self.read_user.id
                )._workspace_preview_payload(self.read_user)

        document.storage_policy_id.workspace_enabled = False
        with self.assertRaises(AccessError):
            document.with_context(
                lhi_workspace_user_id=self.read_user.id
            )._workspace_preview_payload(self.read_user)

    def test_focus_refresh_detects_newer_version(self):
        document = self._document()

        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_request",
            return_value=self._remote_payload(document),
        ):
            refreshed = self.project.with_user(
                self.edit_user
            ).lhi_workspace_refresh([document.uuid])
        self.assertTrue(refreshed[0]["newer"])
        self.assertEqual(refreshed[0]["modified_by"], "Entra User")
        self.assertEqual(refreshed[0]["etag"], '"etag-2"')

    def test_version_history_is_paginated_and_bounded(self):
        document = self._document()
        versions = [
            {
                "id": "3.0",
                "size": 256,
                "lastModifiedDateTime": "2026-07-16T10:00:00Z",
                "lastModifiedBy": {"user": {"displayName": "Editor"}},
            }
        ]
        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_get_all",
            return_value=versions,
        ) as graph_get_all:
            result = self.project.with_user(
                self.read_user
            ).lhi_workspace_versions(document.uuid)
        self.assertEqual(result[0]["id"], "3.0")
        self.assertEqual(graph_get_all.call_args.kwargs["max_pages"], 10)
        self.assertEqual(graph_get_all.call_args.kwargs["max_items"], 100)

    def test_templates_are_admin_managed_and_model_scoped(self):
        template = self.env["lhi.document.template"].create(
            {
                "name": "Project Word Template",
                "company_id": self.env.company.id,
                "graph_connection_id": self.connection.id,
                "model_name": "lhi.project",
                "file_type": "word",
                "source_drive_id": "template-drive",
                "source_item_id": "template-item",
                "source_name": "Project Template.docx",
                "source_mime_type": (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                "source_size": 100,
                "state": "approved",
            }
        )
        result = self.project.with_user(self.edit_user).lhi_workspace_templates()
        self.assertEqual(result[0]["id"], template.id)
        with self.assertRaises(AccessError):
            self.env["lhi.document.template"].with_user(self.read_user).search([])
        auditor = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Workspace Auditor",
                "login": "workspace.auditor@example.invalid",
                "company_id": self.env.company.id,
                "company_ids": [Command.set(self.env.company.ids)],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "lhi_security.group_lhi_internal_auditor"
                            ).id,
                        ]
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            template.with_user(auditor).action_validate_and_approve()

    def test_create_from_template_is_delegated_idempotent_and_fail_closed(self):
        template = self.env["lhi.document.template"].create(
            {
                "name": "Project Word Template",
                "company_id": self.env.company.id,
                "graph_connection_id": self.connection.id,
                "model_name": "lhi.project",
                "file_type": "word",
                "source_drive_id": "template-drive",
                "source_item_id": "template-item",
                "source_name": "Project Template.docx",
                "source_mime_type": (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                "source_size": 8,
                "state": "approved",
            }
        )
        content = b"template"
        created_payload = {
            "id": "created-from-template",
            "name": "Quarterly Report.docx",
            "size": len(content),
            "eTag": '"template-etag"',
            "cTag": '"template-version"',
            "webUrl": (
                "https://tenant.sharepoint.com/projects/Quarterly%20Report.docx"
            ),
            "lastModifiedDateTime": "2026-07-16T10:00:00Z",
            "lastModifiedBy": {"user": {"displayName": "Template User"}},
            "parentReference": {"driveId": "project-drive", "id": "target-parent"},
            "file": {"mimeType": template.source_mime_type, "hashes": {}},
        }
        graph_calls = []

        def graph_request(connection, method, resource, **kwargs):
            graph_calls.append((method, resource, kwargs))
            if "template-item" in resource:
                return {
                    "id": "template-item",
                    "name": template.source_name,
                    "size": len(content),
                    "file": {"mimeType": template.source_mime_type},
                    "@microsoft.graph.downloadUrl": (
                        "https://tenant.sharepoint.com/download/template"
                    ),
                }
            if method == "GET":
                return created_payload
            return {}

        with (
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "graph_request",
                graph_request,
            ),
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "lhi_upload_session_request",
                return_value=SimpleNamespace(content=content),
            ),
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "lhi_ensure_folder_path",
                return_value="target-parent",
            ),
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "lhi_upload_small",
                return_value=created_payload,
            ),
        ):
            first = self.project.with_user(
                self.edit_user
            ).lhi_workspace_create_from_template(
                template.id, "Quarterly Report", "same-browser-request"
            )
            second = self.project.with_user(
                self.edit_user
            ).lhi_workspace_create_from_template(
                template.id, "Quarterly Report", "same-browser-request"
            )
        self.assertEqual(first["uuid"], second["uuid"])
        self.assertEqual(first["storage_state"], "available")
        self.assertIn("web=1", first["edit_url"])
        self.assertEqual(
            self.env["lhi.document.item"].sudo().search_count(
                [("sharepoint_item_id", "=", "created-from-template")]
            ),
            1,
        )
        self.assertTrue(
            all(
                call[2].get("auth_context") == "delegated"
                for call in graph_calls
                if call[0] in ("GET", "PATCH")
            )
        )

    def test_version_confirmation_keeps_same_item_and_checks_policy(self):
        document = self._document()
        document.sudo().write({"upload_state": "session"})
        payload = self._remote_payload(document)
        payload["size"] = 512
        with (
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "graph_request",
                return_value=payload,
            ),
            patch.object(
                self.env.registry["lhi.document.item"],
                "_calculate_remote_hashes",
                return_value=True,
            ),
            patch.object(
                self.env.registry["lhi.document.item"],
                "_patch_sharepoint_metadata",
                return_value=True,
            ),
        ):
            refreshed = document.with_user(
                self.edit_user
            )._workspace_confirm_version(document.sharepoint_item_id)
        self.assertEqual(refreshed["storage_state"], "available")
        self.assertEqual(document.file_size, 512)
        self.assertEqual(document.sharepoint_item_id, "item-lhi.project-%s" % self.project.id)

        with self.assertRaises(ValidationError):
            document.with_user(self.edit_user)._workspace_confirm_version(
                "different-item"
            )

    def test_version_confirmation_requires_a_changed_etag(self):
        document = self._document(upload_state="session")
        payload = self._remote_payload(document, etag=document.sharepoint_etag)
        with patch.object(
            self.env.registry["lhi.graph.connection"],
            "graph_request",
            return_value=payload,
        ):
            with self.assertRaises(ValidationError):
                document.with_user(self.edit_user)._workspace_confirm_version(
                    document.sharepoint_item_id
                )
