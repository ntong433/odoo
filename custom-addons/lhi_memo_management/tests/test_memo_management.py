import hashlib
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestMemoManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.employee_group = cls.env.ref("lhi_security.group_lhi_employee")
        cls.memo_privilege = cls.env.ref("lhi_memo_management.privilege_lhi_memo")
        cls.approver_group = cls.env["res.groups"].create(
            {
                "name": "Memo Test Approver",
                "privilege_id": cls.memo_privilege.id,
            }
        )
        cls.final_group = cls.env["res.groups"].create(
            {
                "name": "Memo Test Final Authority",
                "privilege_id": cls.memo_privilege.id,
            }
        )
        cls.department = cls.env["lhi.department"].create(
            {
                "name": "Memo Test Department",
                "code": "MEMO-TEST",
                "company_id": cls.company.id,
            }
        )
        cls.other_department = cls.env["lhi.department"].create(
            {
                "name": "Other Memo Test Department",
                "code": "MEMO-OTHER",
                "company_id": cls.company.id,
            }
        )
        cls.requester = cls._new_employee(
            "memo_requester",
            "Memo Requester",
            cls.department,
            "11111111-1111-4111-8111-111111111111",
        )
        cls.approver = cls._new_employee(
            "memo_approver",
            "Memo Approver",
            cls.department,
            "22222222-2222-4222-8222-222222222222",
            cls.approver_group,
        )
        cls.final_authority = cls._new_employee(
            "memo_final_authority",
            "Memo Final Authority",
            cls.department,
            "33333333-3333-4333-8333-333333333333",
            cls.final_group,
        )
        cls.other_user = cls._new_employee(
            "memo_other_user",
            "Memo Other User",
            cls.other_department,
            "44444444-4444-4444-8444-444444444444",
        )

        cls.matrix = cls.env["lhi.approval.matrix"].create(
            {
                "name": "Memo Test Sequential Route",
                "document_type": "memo",
                "company_id": cls.company.id,
                "currency_id": cls.company.currency_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Department Approval",
                            "sequence": 10,
                            "approver_group_id": cls.approver_group.id,
                            "approver_ids": [(6, 0, cls.approver.ids)],
                            "approval_type": "any",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Final Authority",
                            "sequence": 20,
                            "approver_group_id": cls.final_group.id,
                            "approver_ids": [(6, 0, cls.final_authority.ids)],
                            "approval_type": "any",
                        },
                    ),
                ],
            }
        )
        cls.category = cls.env["lhi.memo.category"].create(
            {
                "name": "Memo Test Category",
                "code": "MEMO-TEST-CATEGORY",
                "company_id": cls.company.id,
                "approval_matrix_id": cls.matrix.id,
                "requester_signature_required": True,
                "final_signature_required": True,
            }
        )
        cls.connection = cls.env["lhi.graph.connection"].search(
            [("company_id", "=", cls.company.id), ("active", "=", True)],
            limit=1,
        )
        if not cls.connection:
            cls.connection = cls.env["lhi.graph.connection"].create(
                {
                    "name": "Memo Test Graph",
                    "company_id": cls.company.id,
                    "sharepoint_site_id": (
                        "tenant.sharepoint.com,"
                        "00000000-0000-4000-8000-000000000001,"
                        "00000000-0000-4000-8000-000000000002"
                    ),
                }
            )
        cls.configuration = cls.env["lhi.opensign.configuration"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        config_values = {
            "name": "Memo Test LHI Sign",
            "api_base_url": "https://sign.example.test/api/v1.2/",
            "allowed_preparation_hosts": "sign.example.test",
            "allowed_download_hosts": "sign.example.test",
            "active": True,
        }
        if cls.configuration:
            cls.configuration.write(config_values)
        else:
            cls.configuration = cls.env["lhi.opensign.configuration"].create(
                {"company_id": cls.company.id, **config_values}
            )

    @classmethod
    def _new_employee(cls, login, name, department, object_id, extra_group=False):
        groups = ["base.group_user", "lhi_security.group_lhi_employee"]
        if extra_group:
            xmlids = extra_group.get_external_id()
            xmlid = xmlids.get(extra_group.id)
            if xmlid:
                groups.append(xmlid)
        user = new_test_user(
            cls.env,
            login=login,
            name=name,
            email=f"{login}@example.test",
            groups=",".join(groups),
        )
        if extra_group and extra_group not in user.group_ids:
            user.write({"group_ids": [(4, extra_group.id)]})
        user.write(
            {
                "entra_object_id": object_id,
                "entra_tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "entra_upn": f"{login}@example.test",
                "lhi_department_ids": [(6, 0, department.ids)],
            }
        )
        return user

    def setUp(self):
        super().setUp()
        self.spool = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"LHI_SHAREPOINT_SPOOL_DIR": self.spool.name}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.spool.cleanup)

    @staticmethod
    def _confirm_upload(documents):
        for document in documents:
            document.sudo().write(
                {
                    "sharepoint_site_id": "memo-test-site",
                    "sharepoint_drive_id": "memo-test-drive",
                    "sharepoint_item_id": f"memo-test-item-{document.id}",
                    "sharepoint_web_url": (
                        f"https://tenant.sharepoint.com/memo-test-item-{document.id}"
                    ),
                    "storage_state": "available",
                    "upload_state": "completed",
                }
            )
            document._remove_spool()
        return True

    def _create_memo(self, requester=None, department=None, **extra):
        requester = requester or self.requester
        department = department or self.department
        values = {
            "title": "Office Operations Memo",
            "memo_category_id": self.category.id,
            "subject": "Routine office requirement",
            "purpose": "Request approval for a standalone departmental need.",
            "department_id": department.id,
            **extra,
        }
        with patch.object(
            self.env.registry["lhi.document.item"],
            "action_upload",
            self._confirm_upload,
        ):
            return self.env["lhi.memo"].with_user(requester).create(values)

    def _capture_pdf(
        self,
        memo,
        pdf=b"%PDF-1.7\nMemo test\n%%EOF",
        *,
        version='"memo-version-1"',
        etag='"memo-etag-1"',
    ):
        metadata = {
            "id": memo.source_docx_item_id.sharepoint_item_id,
            "name": memo.source_docx_item_id.name,
            "size": 1024,
            "eTag": etag,
            "cTag": version,
            "webUrl": memo.source_docx_web_url,
            "parentReference": {"driveId": "memo-test-drive", "id": "parent"},
            "file": {"hashes": {}},
        }
        metadata_results = [dict(metadata), dict(metadata)]
        binary_results = [
            SimpleNamespace(content=b"PK\x03\x04latest-word-version"),
            SimpleNamespace(content=pdf),
        ]

        def graph_request(_records, *_args, **_kwargs):
            return metadata_results.pop(0)

        def binary_request(_records, *_args, **_kwargs):
            return binary_results.pop(0)

        with (
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "graph_request",
                graph_request,
            ),
            patch.object(
                self.env.registry["lhi.graph.connection"],
                "lhi_binary_request",
                binary_request,
            ),
            patch.object(
                self.env.registry["lhi.document.item"],
                "action_upload",
                self._confirm_upload,
            ),
        ):
            return memo._capture_current_pdf()

    def _signature_request(self, memo):
        pdf_item, pdf_hash = self._capture_pdf(memo)
        _approval, lines = memo._prepare_approval_route()
        return memo._create_signature_request(lines, pdf_item, pdf_hash)

    def _prepare_provider(self, signature_request):
        response = {
            "document_id": f"provider-{signature_request.id}",
            "url": "https://sign.example.test/preparation/secure",
        }
        with patch.object(
            self.env.registry["lhi.opensign.configuration"],
            "api_request",
            return_value=response,
        ) as api_request:
            signature_request.action_create_provider_draft()
            signature_request.action_create_provider_draft()
        self.assertEqual(api_request.call_count, 1)
        if signature_request.memo_id and signature_request.memo_id.state != "preparing":
            signature_request.memo_id.sudo().write({"state": "preparing"})
        return signature_request

    def _event(self, signature_request, event_type, suffix):
        return (
            self.env["lhi.opensign.webhook.event"]
            .sudo()
            .create(
                {
                    "provider_event_id": f"memo-test-{signature_request.id}-{suffix}",
                    "request_id": signature_request.id,
                    "event_type": event_type,
                    "payload_digest": hashlib.sha256(suffix.encode()).hexdigest(),
                }
            )
        )

    def test_employee_creates_standalone_word_memo(self):
        memo = self._create_memo()
        self.assertRegex(memo.name, r"^LHI/MEMO/\d{4}/\d+$")
        self.assertEqual(memo.work_context, "standalone_departmental")
        self.assertFalse(memo.project_id)
        self.assertFalse(memo.grant_id)
        self.assertEqual(memo.state, "authoring")
        self.assertEqual(memo.source_docx_item_id.storage_state, "available")
        self.assertTrue(memo.source_docx_item_id.sharepoint_item_id)
        self.assertEqual(memo.action_open_word()["url"], memo.source_docx_web_url)

    def test_navigation_exposes_memos_but_not_signature_administration(self):
        memo_menu = self.env.ref("lhi_memo_management.menu_lhi_memo_root")
        signature_menu = self.env.ref("lhi_signature_bridge.menu_lhi_opensign")
        visible_menu_ids = (
            self.env["ir.ui.menu"].with_user(self.requester)._visible_menu_ids()
        )
        self.assertIn(memo_menu.id, visible_menu_ids)
        self.assertNotIn(signature_menu.id, visible_menu_ids)
        apps = (
            self.env["lhi.dashboard.widget"]
            .with_user(self.requester)
            .get_accessible_apps()["apps"]
        )
        self.assertEqual(
            len([app for app in apps if app["key"] == "memos"]),
            1,
        )
        self.assertFalse(any(app["key"] == "signatures" for app in apps))
        quick_actions = (
            self.env["lhi.dashboard.widget"]
            .with_user(self.requester)
            .get_quick_actions()
        )
        self.assertTrue(any(action["id"] == "raise_memo" for action in quick_actions))
        signature_admin = new_test_user(
            self.env,
            login="memo_signature_admin",
            groups=("base.group_user,lhi_signature_bridge.group_lhi_signature_admin"),
        )
        admin_visible_menu_ids = (
            self.env["ir.ui.menu"].with_user(signature_admin)._visible_menu_ids()
        )
        self.assertIn(signature_menu.id, admin_visible_menu_ids)

    def test_erp_administrator_has_employee_memo_access_and_protected_roles(self):
        administrator = self.env.ref("base.user_admin")
        memo_menu = self.env.ref("lhi_memo_management.menu_lhi_memo_root")
        erp_admin_group = self.env.ref("lhi_security.group_lhi_erp_admin")
        memo_admin_group = self.env.ref(
            "lhi_memo_management.group_lhi_memo_admin"
        )

        self.assertTrue(
            administrator.has_group("lhi_security.group_lhi_erp_admin")
        )
        self.assertTrue(administrator.has_group("lhi_security.group_lhi_manager"))
        self.assertTrue(administrator.has_group("lhi_security.group_lhi_employee"))
        self.assertTrue(
            self.env["lhi.memo"]
            .with_user(administrator)
            .check_access_rights("read", raise_exception=False)
        )
        visible_menu_ids = (
            self.env["ir.ui.menu"]
            .with_user(administrator)
            ._visible_menu_ids()
        )
        self.assertIn(memo_menu.id, visible_menu_ids)

        protected_groups = self.env["res.groups"]._lhi_entra_protected_groups()
        self.assertIn(erp_admin_group, protected_groups)
        self.assertIn(memo_admin_group, protected_groups)

    def test_exact_word_version_is_captured_and_hashed(self):
        memo = self._create_memo()
        pdf = b"%PDF-1.7\nTwo-page representative payload\n%%EOF"
        pdf_item, pdf_hash = self._capture_pdf(memo, pdf=pdf)
        self.assertEqual(memo.source_docx_version_id, '"memo-version-1"')
        self.assertEqual(memo.source_docx_etag, '"memo-etag-1"')
        self.assertEqual(pdf_hash, hashlib.sha256(pdf).hexdigest())
        self.assertEqual(pdf_item.storage_state, "available")
        self.assertEqual(memo.action_preview_document()["target"], "new")

    def test_one_and_multi_page_pdf_captures_use_dynamic_preparation(self):
        for page_count in (1, 3):
            memo = self._create_memo(title=f"{page_count}-page Memo")
            pdf = (
                b"%PDF-1.7\n1 0 obj<</Type/Pages/Count "
                + str(page_count).encode()
                + b">>endobj\n%%EOF"
            )
            pdf_item, _pdf_hash = self._capture_pdf(memo, pdf=pdf)
            signature_request = memo._create_signature_request(
                memo._prepare_approval_route()[1], pdf_item, memo.source_pdf_hash
            )
            self.assertEqual(signature_request.sequence_type, "sequential")
            self.assertTrue(
                all(
                    not signer["widgets"]
                    for signer in signature_request._provider_signers()
                )
            )

    def test_strict_route_and_provider_draft_are_idempotent(self):
        memo = self._create_memo()
        signature_request = self._signature_request(memo)
        recipients = signature_request.recipient_ids.sorted("sequence")
        self.assertEqual(recipients[0].user_id, self.requester)
        self.assertEqual(recipients[0].participant_role, "requester")
        self.assertEqual(recipients[-1].user_id, self.final_authority)
        self.assertEqual(recipients[-1].participant_role, "final_signer")
        self.assertEqual(recipients[1].provider_role, "approver")
        same_request = memo._create_signature_request(
            memo.approver_line_ids,
            memo.source_pdf_item_id,
            memo.source_pdf_hash,
        )
        self.assertEqual(same_request, signature_request)
        self._prepare_provider(signature_request)
        self.assertEqual(signature_request.status, "preparing")
        self.assertNotIn("token", signature_request.provider_preparation_url)

    def test_failed_provider_creation_never_marks_request_sent(self):
        memo = self._create_memo()
        signature_request = self._signature_request(memo)
        with (
            patch.object(
                self.env.registry["lhi.opensign.configuration"],
                "api_request",
                side_effect=UserError(
                    "LHI Sign did not confirm the request; its outcome is unknown."
                ),
            ),
            self.assertRaises(UserError),
        ):
            signature_request.action_create_provider_draft()
        self.assertFalse(signature_request.provider_request_id)
        self.assertEqual(signature_request.status, "failed")
        self.assertTrue(signature_request.provider_creation_uncertain)
        self.assertNotIn(signature_request.status, ("sent", "in_progress"))
        with self.assertRaises(AccessError):
            signature_request.with_user(
                self.requester
            ).action_reset_uncertain_creation()
        signature_admin = new_test_user(
            self.env,
            login="memo_uncertain_signature_admin",
            groups=("base.group_user,lhi_signature_bridge.group_lhi_signature_admin"),
        )
        signature_request.with_user(signature_admin).action_reset_uncertain_creation()
        self.assertEqual(signature_request.status, "draft")
        self.assertFalse(signature_request.provider_creation_uncertain)

    def test_required_widgets_are_enforced_without_fixed_coordinates(self):
        memo = self._create_memo()
        signature_request = self._signature_request(memo)
        with self.assertRaises(UserError):
            signature_request._validate_required_widgets(
                {
                    "signers": [
                        {"email": recipient.email, "widgets": []}
                        for recipient in signature_request.recipient_ids
                    ]
                }
            )
        signers = []
        for recipient in signature_request.recipient_ids:
            widgets = []
            if recipient.required_widget_types:
                widgets = [
                    {"type": "signature"},
                    {"type": "name"},
                    {"type": "date"},
                ]
            signers.append({"email": recipient.email, "widgets": widgets})
        self.assertTrue(
            signature_request._validate_required_widgets({"signers": signers})
        )
        self.assertTrue(
            all(
                not signer["widgets"]
                for signer in signature_request._provider_signers()
            )
        )

    def test_immutable_entra_identity_and_sequence_gate_signing_url(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        signature_request.sudo().write(
            {
                "preparation_completed": True,
                "current_recipient_id": signature_request.recipient_ids[0].id,
            }
        )
        payload = {
            "signers": [
                {
                    "email": self.requester.email,
                    "url": "https://sign.example.test/sign/current",
                }
            ]
        }
        with patch.object(
            self.env.registry["lhi.opensign.configuration"],
            "api_request",
            return_value=payload,
        ):
            self.assertEqual(
                signature_request.signing_url_for_user(self.requester),
                "https://sign.example.test/sign/current",
            )
            with self.assertRaises(AccessError):
                signature_request.signing_url_for_user(self.approver)
            old_object_id = self.requester.entra_object_id
            self.requester.sudo().write(
                {"entra_object_id": "55555555-5555-4555-8555-555555555555"}
            )
            try:
                with self.assertRaises(AccessError):
                    signature_request.signing_url_for_user(self.requester)
            finally:
                self.requester.sudo().write({"entra_object_id": old_object_id})

    def test_provider_events_drive_sequential_approval_and_completion(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        recipients = signature_request.recipient_ids.sorted("sequence")
        signature_request.sudo().write(
            {
                "preparation_completed": True,
                "status": "requester_signature_pending",
                "current_recipient_id": recipients[0].id,
            }
        )
        with self.assertRaises(UserError):
            signature_request.process_provider_event(
                self._event(signature_request, "signed", "early-final"),
                {"event": "signed", "signer": {"email": recipients[-1].email}},
            )
        for index, recipient in enumerate(recipients):
            signature_request.process_provider_event(
                self._event(signature_request, "signed", f"signed-{index}"),
                {"event": "signed", "signer": {"email": recipient.email}},
            )
        self.assertEqual(memo.approval_request_id.state, "approved")
        self.assertEqual(memo.state, "final_signature_pending")
        self.assertTrue(memo.requester_signature_completed)
        self.assertTrue(memo.final_signature_completed)

        with (
            patch.object(
                self.env.registry["lhi.opensign.configuration"],
                "download_artifact",
                side_effect=[b"%PDF-signed-memo", b"%PDF-audit-certificate"],
            ),
            patch.object(
                self.env.registry["lhi.document.item"],
                "action_upload",
                self._confirm_upload,
            ),
        ):
            signature_request.process_provider_event(
                self._event(signature_request, "completed", "completed"),
                {
                    "event": "completed",
                    "file": "https://sign.example.test/files/signed",
                    "certificate": "https://sign.example.test/files/certificate",
                },
            )
        self.assertEqual(memo.state, "completed")
        self.assertEqual(
            memo.signed_pdf_hash, hashlib.sha256(b"%PDF-signed-memo").hexdigest()
        )
        self.assertEqual(memo.signed_pdf_item_id.storage_state, "available")
        self.assertEqual(memo.certificate_item_id.storage_state, "available")
        self.assertFalse(signature_request.signed_pdf)
        self.assertFalse(signature_request.audit_certificate)

    def test_reconciliation_repairs_a_missed_completion_webhook(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        recipients = signature_request.recipient_ids.sorted("sequence")
        signature_request.sudo().write(
            {
                "preparation_completed": True,
                "status": "requester_signature_pending",
                "current_recipient_id": recipients[0].id,
            }
        )
        memo.sudo().write({"state": "requester_signature_pending"})
        provider_payload = {
            "objectId": signature_request.provider_request_id,
            "status": "completed",
            "signers": [
                {"email": recipient.email, "status": "completed"}
                for recipient in recipients
            ],
            "file": "https://sign.example.test/files/reconciled-signed",
            "certificate": "https://sign.example.test/files/reconciled-certificate",
        }
        with (
            patch.object(
                self.env.registry["lhi.opensign.configuration"],
                "api_request",
                return_value=provider_payload,
            ),
            patch.object(
                self.env.registry["lhi.opensign.configuration"],
                "download_artifact",
                side_effect=[b"%PDF-reconciled-signed", b"%PDF-reconciled-certificate"],
            ),
            patch.object(
                self.env.registry["lhi.document.item"],
                "action_upload",
                self._confirm_upload,
            ),
        ):
            signature_request.action_reconcile()

        self.assertEqual(signature_request.status, "completed")
        self.assertEqual(memo.state, "completed")
        self.assertEqual(
            signature_request.recipient_ids.mapped("status"),
            ["completed"] * len(recipients),
        )

    def test_return_supersedes_request_and_preserves_history(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        recipients = signature_request.recipient_ids.sorted("sequence")
        signature_request.sudo().write(
            {
                "preparation_completed": True,
                "status": "requester_signature_pending",
                "current_recipient_id": recipients[0].id,
            }
        )
        signature_request.process_provider_event(
            self._event(signature_request, "signed", "requester-signed"),
            {"event": "signed", "signer": {"email": recipients[0].email}},
        )
        old_pdf = memo.source_pdf_item_id
        memo.with_user(self.approver).write({"return_reason": "Correct the amount."})
        with patch.object(
            self.env.registry["lhi.opensign.configuration"],
            "api_request",
            return_value={},
        ):
            memo.with_user(self.approver).action_return_for_correction()
        self.assertEqual(memo.state, "returned")
        self.assertFalse(memo.signature_request_id)
        self.assertIn(signature_request, memo.signature_request_ids)
        self.assertEqual(signature_request.status, "superseded")
        self.assertEqual(memo.source_pdf_item_id, old_pdf)
        self.assertFalse(memo.requester_signature_completed)

        new_pdf, new_hash = self._capture_pdf(
            memo,
            pdf=b"%PDF-1.7\nCorrected memo\n%%EOF",
            version='"memo-version-2"',
            etag='"memo-etag-2"',
        )
        _approval_request, new_lines = memo._prepare_approval_route()
        replacement = memo._create_signature_request(new_lines, new_pdf, new_hash)
        self.assertNotEqual(replacement, signature_request)
        self.assertNotEqual(
            replacement.source_pdf_hash, signature_request.source_pdf_hash
        )
        self.assertEqual(replacement.supersedes_request_id, signature_request)
        self.assertEqual(signature_request.superseded_by_request_id, replacement)
        self.assertEqual(memo.source_docx_version_id, '"memo-version-2"')
        self.assertFalse(memo.requester_signature_completed)
        self.assertEqual(
            replacement.recipient_ids.sorted("sequence")[:1].participant_role,
            "requester",
        )

    def test_duplicate_webhook_event_is_idempotent(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        raw = b'{"event":"created","objectId":"provider-test"}'
        payload = {"event": "created", "objectId": "provider-test"}
        first, duplicate_first = (
            self.env["lhi.opensign.webhook.event"]
            .sudo()
            .receive(signature_request, payload, raw)
        )
        second, duplicate_second = (
            self.env["lhi.opensign.webhook.event"]
            .sudo()
            .receive(signature_request, payload, raw)
        )
        self.assertFalse(duplicate_first)
        self.assertTrue(duplicate_second)
        self.assertEqual(first, second)
        self.assertEqual(first.state, "processed")

    def test_webhook_event_id_cannot_be_replayed_with_changed_payload(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        payload = {
            "event": "created",
            "eventId": "immutable-provider-event",
            "objectId": signature_request.provider_request_id,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.env["lhi.opensign.webhook.event"].sudo().receive(
            signature_request, payload, raw
        )

        changed_payload = {**payload, "unexpected": "changed"}
        changed_raw = json.dumps(
            changed_payload, sort_keys=True, separators=(",", ":")
        ).encode()
        with self.assertRaises(ValidationError):
            self.env["lhi.opensign.webhook.event"].sudo().receive(
                signature_request, changed_payload, changed_raw
            )

    def test_failed_webhook_rolls_back_partial_workflow_changes(self):
        memo = self._create_memo()
        signature_request = self._prepare_provider(self._signature_request(memo))
        requester_recipient = signature_request.recipient_ids.sorted("sequence")[:1]
        signature_request.sudo().write(
            {
                "preparation_completed": True,
                "status": "requester_signature_pending",
                "current_recipient_id": requester_recipient.id,
            }
        )
        memo.sudo().write({"state": "requester_signature_pending"})
        payload = {
            "event": "signed",
            "eventId": "provider-event-that-fails-locally",
            "objectId": signature_request.provider_request_id,
            "signer": {"email": requester_recipient.email},
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

        with patch.object(
            self.env.registry["lhi.memo"],
            "opensign_event_hook",
            side_effect=UserError("simulated local failure"),
        ):
            event, duplicate = (
                self.env["lhi.opensign.webhook.event"]
                .sudo()
                .receive(signature_request, payload, raw)
            )

        self.assertFalse(duplicate)
        self.assertEqual(event.state, "failed")
        self.assertEqual(requester_recipient.status, "pending")
        self.assertEqual(signature_request.current_recipient_id, requester_recipient)
        self.assertEqual(signature_request.status, "requester_signature_pending")

    def test_security_is_department_scoped_and_technical_requests_are_restricted(self):
        own_memo = self._create_memo()
        signature_request = self._signature_request(own_memo)
        other_memo = self._create_memo(
            requester=self.other_user,
            department=self.other_department,
            title="Other Department Memo",
        )
        department_manager = self._new_employee(
            "memo_department_manager",
            "Memo Department Manager",
            self.department,
            "66666666-6666-4666-8666-666666666666",
            self.env.ref("lhi_memo_management.group_lhi_department_memo_manager"),
        )
        visible = (
            self.env["lhi.memo"]
            .with_user(department_manager)
            .search([("id", "=", other_memo.id)])
        )
        self.assertFalse(visible)
        self.assertFalse(
            self.env["lhi.opensign.request"]
            .with_user(self.requester)
            .check_access_rights("read", raise_exception=False)
        )
        with self.assertRaises(AccessError):
            signature_request.with_user(self.requester).write({"res_id": other_memo.id})
        with self.assertRaises(AccessError):
            own_memo.source_docx_item_id.with_user(self.other_user).check_linked_access(
                "read"
            )
        self.assertIn(
            "lhi_signature_bridge.group_lhi_signature_admin",
            self.env["lhi.memo"]._fields["source_pdf_hash"].groups,
        )
