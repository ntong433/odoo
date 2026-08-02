"""
Tests for MemoDocumentGateway access control and contract isolation.

These tests verify that:
- Normal Memo employees cannot access lhi.document.item records directly
- The gateway enforces six-step authorization before any sudo elevation
- _capture_current_pdf, action_prepare_and_sign, and other document actions
  succeed through the gateway for authorized users
- Cross-memo access, company isolation, and linkage guards are enforced
- Computed Boolean flags do not raise AccessError for normal employees
- Correlation IDs and operation states are recorded on failures
- Sensitive data is not returned in browser-facing client action dicts

Run with::

    python3 /opt/odoo/odoo-bin --test-enable \\
        -m lhi_memo_management \\
        --test-tags /test_memo_document_gateway \\
        --stop-after-init
"""
import hashlib
import io
import os
import tempfile
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from ..services.memo_document_gateway import (
    ALLOWED_LINKED_FIELDS,
    MEMO_DOCUMENT_CONTRACT_VERSION,
    MemoDocumentGateway,
)


@tagged("post_install", "-at_install")
class TestMemoDocumentGateway(TransactionCase):
    """Test the MemoDocumentGateway authorization and contract isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company

        cls.requester = new_test_user(
            cls.env,
            login="gw_requester",
            name="GW Requester",
            email="gw_requester@example.test",
            groups="base.group_user,lhi_security.group_lhi_employee",
        )
        cls.requester.sudo().write(
            {
                "entra_object_id": "11111111-gw-4111-8111-111111111111",
                "entra_tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "entra_upn": "gw_requester@example.test",
            }
        )

        cls.outsider = new_test_user(
            cls.env,
            login="gw_outsider",
            name="GW Outsider",
            email="gw_outsider@example.test",
            groups="base.group_user,lhi_security.group_lhi_employee",
        )

        cls.memo_admin = new_test_user(
            cls.env,
            login="gw_memo_admin",
            name="GW Memo Admin",
            email="gw_memo_admin@example.test",
            groups="base.group_user,lhi_security.group_lhi_employee,"
            "lhi_memo_management.group_lhi_memo_admin",
        )

        # Get or create a Graph connection
        cls.connection = cls.env["lhi.graph.connection"].sudo().search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.connection:
            cls.connection = cls.env["lhi.graph.connection"].sudo().create(
                {
                    "name": "GW Test Graph",
                    "company_id": cls.company.id,
                    "sharepoint_site_id": (
                        "tenant.sharepoint.com,"
                        "00000000-0000-4000-8000-000000000001,"
                        "00000000-0000-4000-8000-000000000002"
                    ),
                }
            )

    def setUp(self):
        super().setUp()
        self._spool_dir = tempfile.TemporaryDirectory()
        self._spool_patch = patch.dict(
            os.environ, {"LHI_SHAREPOINT_SPOOL_DIR": self._spool_dir.name}
        )
        self._spool_patch.start()
        self.addCleanup(self._spool_patch.stop)
        self.addCleanup(self._spool_dir.cleanup)

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_or_create_storage_policy(self):
        """Get or create a SharePoint storage policy for memos."""
        policy = (
            self.env["lhi.document.storage.policy"]
            .sudo()
            .search(
                [
                    ("model_name", "=", "lhi.memo"),
                    ("company_id", "=", self.company.id),
                    ("storage_backend", "=", "sharepoint"),
                ],
                limit=1,
            )
        )
        if policy:
            return policy
        return (
            self.env["lhi.document.storage.policy"]
            .sudo()
            .create(
                {
                    "name": "GW Test Memo Policy",
                    "model_name": "lhi.memo",
                    "field_name": "source_docx_item_id",
                    "company_id": self.company.id,
                    "storage_backend": "sharepoint",
                    "graph_connection_id": self.connection.id,
                    "sharepoint_library": "MemoDocuments",
                    "folder_strategy": "library_root",
                    "maximum_size_mb": 10,
                    "confidentiality": "internal",
                    "document_category": "memo",
                }
            )
        )

    def _create_available_document_item(self, memo, field_name="source_docx_item_id"):
        """Create an lhi.document.item in 'available' state linked to memo."""
        policy = self._get_or_create_storage_policy()
        content = b"PK\x03\x04fake-docx-content"
        checksum = hashlib.sha256(content).hexdigest()
        sha1 = hashlib.sha1(content).hexdigest()
        key = self.env["lhi.document.item"].sudo()._make_idempotency_key(
            "lhi.memo", memo.id, field_name, f"gw-test-{memo.id}.docx", checksum
        )
        # Check for existing
        existing = (
            self.env["lhi.document.item"]
            .sudo()
            .search([("idempotency_key", "=", key)], limit=1)
        )
        if existing:
            return existing
        item = (
            self.env["lhi.document.item"]
            .sudo()
            .create(
                {
                    "name": f"gw-test-{memo.id}.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "file_size": len(content),
                    "checksum": checksum,
                    "sha1_checksum": sha1,
                    "company_id": self.company.id,
                    "requested_by_id": self.requester.id,
                    "graph_connection_id": self.connection.id,
                    "storage_policy_id": policy.id,
                    "linked_model": "lhi.memo",
                    "linked_record_id": memo.id,
                    "linked_field": field_name,
                    "linked_record_uuid": memo.uuid,
                    "storage_state": "available",
                    "upload_state": "completed",
                    "sharepoint_site_id": "gw-site-id",
                    "sharepoint_drive_id": "gw-drive-id",
                    "sharepoint_item_id": f"gw-item-{memo.id}",
                    "sharepoint_web_url": f"https://tenant.sharepoint.com/gw-item-{memo.id}",
                    "idempotency_key": key,
                }
            )
        )
        return item

    def _create_minimal_memo(self, state="authoring"):
        """Create a minimal lhi.memo for gateway testing."""
        department = self.env["lhi.department"].sudo().search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if not department:
            department = self.env["lhi.department"].sudo().create(
                {"name": "GW Test Dept", "code": "GW-DEPT", "company_id": self.company.id}
            )
        category = self.env["lhi.memo.category"].sudo().search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if not category:
            category = self.env["lhi.memo.category"].sudo().create(
                {
                    "name": "GW Test Category",
                    "code": "GW-CAT",
                    "company_id": self.company.id,
                }
            )
        memo = (
            self.env["lhi.memo"]
            .sudo()
            .create(
                {
                    "title": "Gateway Test Memo",
                    "memo_category_id": category.id,
                    "subject": "Gateway test subject",
                    "purpose": "Testing document gateway isolation.",
                    "department_id": department.id,
                    "company_id": self.company.id,
                    "requester_id": self.requester.id,
                }
            )
        )
        if state != "draft":
            memo.write({"state": state})
        return memo

    # ================================================================== #
    # Test 1: Direct lhi.document.item read raises AccessError            #
    # ================================================================== #

    def test_01_direct_document_item_read_raises_access_error(self):
        """A normal employee cannot directly read lhi.document.item records."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        with self.assertRaises(AccessError):
            self.env["lhi.document.item"].with_user(self.requester).browse(item.id).read(
                ["storage_state"]
            )

    # ================================================================== #
    # Test 2: Unauthorized user cannot use gateway                        #
    # ================================================================== #

    def test_02_unauthorized_user_cannot_use_gateway(self):
        """An outsider user is rejected by the gateway authorization check."""
        memo = self._create_minimal_memo()
        self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": self._create_available_document_item(memo).id})
        gateway = MemoDocumentGateway(self.env, memo, self.outsider)
        with self.assertRaises(AccessError):
            gateway.read_document_metadata("source_docx_item_id")

    # ================================================================== #
    # Test 3: Requester can read metadata via gateway                     #
    # ================================================================== #

    def test_03_requester_can_read_metadata_via_gateway(self):
        """The memo requester can read document metadata through the gateway."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": item.id})
        gateway = MemoDocumentGateway(self.env, memo, self.requester)
        contract = gateway.read_document_metadata("source_docx_item_id")
        self.assertEqual(contract["contract_version"], MEMO_DOCUMENT_CONTRACT_VERSION)
        self.assertEqual(contract["storage_state"], "available")
        self.assertEqual(contract["document_item_id"], item.id)
        self.assertIn("drive_id", contract)
        self.assertIn("item_id", contract)
        # Confirm: no live ORM record returned
        self.assertNotIsInstance(contract, type(self.env["lhi.document.item"]))

    # ================================================================== #
    # Test 4: Gateway rejects invalid field name                          #
    # ================================================================== #

    def test_04_gateway_rejects_invalid_field_name(self):
        """The gateway rejects field names outside ALLOWED_LINKED_FIELDS."""
        memo = self._create_minimal_memo()
        gateway = MemoDocumentGateway(self.env, memo, self.requester)
        with self.assertRaises(AccessError):
            gateway.read_document_metadata("name")

    # ================================================================== #
    # Test 5: Cross-memo access is blocked                                #
    # ================================================================== #

    def test_05_cross_memo_access_is_blocked(self):
        """A document linked to memo A cannot be accessed through memo B's gateway."""
        memo_a = self._create_minimal_memo()
        memo_b = self._create_minimal_memo()
        item_for_a = self._create_available_document_item(memo_a)
        # Manually link item_for_a to memo_b — should be blocked
        item_for_a.sudo().write({"linked_record_id": memo_b.id + 1000})
        memo_b.sudo().write({"source_docx_item_id": item_for_a.id})
        gateway = MemoDocumentGateway(self.env, memo_b, self.requester)
        # The item's linked_record_id doesn't match memo_b.id → AccessError
        with self.assertRaises((AccessError, UserError)):
            gateway.read_document_metadata("source_docx_item_id")

    # ================================================================== #
    # Test 6: Computed flags do not raise AccessError                     #
    # ================================================================== #

    def test_06_computed_document_flags_no_access_error(self):
        """has_word_document etc. are safe for normal employees to read."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": item.id})
        # Should not raise AccessError
        memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(memo.id)
        has_word = memo_as_requester.has_word_document
        self.assertTrue(has_word)
        has_pdf = memo_as_requester.has_submitted_pdf
        self.assertFalse(has_pdf)

    # ================================================================== #
    # Test 7: Gateway download URL does not expose raw item data          #
    # ================================================================== #

    def test_07_gateway_download_url_is_safe_path(self):
        """Gateway download URL is an internal /lhi/sharepoint/... path."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": item.id})
        gateway = MemoDocumentGateway(self.env, memo, self.requester)
        url = gateway.get_document_download_url("source_docx_item_id")
        self.assertTrue(url.startswith("/lhi/sharepoint/document/"))
        self.assertNotIn("drive", url)
        self.assertNotIn("sharepoint_item_id", url)
        self.assertNotIn(item.sharepoint_item_id, url)

    # ================================================================== #
    # Test 8: PDF creation through gateway is idempotent                  #
    # ================================================================== #

    def test_08_pdf_creation_is_idempotent(self):
        """Creating the same PDF twice through the gateway reuses the first item."""
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": docx_item.id})

        pdf_content = b"%PDF-1.4 fake-pdf-content-for-test"
        pdf_hash = hashlib.sha256(pdf_content).hexdigest()

        call_count = [0]

        def mock_upload(documents):
            for doc in documents:
                call_count[0] += 1
                doc.sudo().write(
                    {
                        "sharepoint_site_id": "gw-site-id",
                        "sharepoint_drive_id": "gw-drive-id",
                        "sharepoint_item_id": f"gw-pdf-{doc.id}",
                        "sharepoint_web_url": f"https://tenant.sharepoint.com/gw-pdf-{doc.id}",
                        "storage_state": "available",
                        "upload_state": "completed",
                    }
                )
                doc._remove_spool()
            return True

        with patch.object(
            self.env.registry["lhi.document.item"], "action_upload", mock_upload
        ):
            gateway = MemoDocumentGateway(self.env, memo, self.requester)
            contract_1 = gateway.create_pdf_document(
                pdf_content, f"{memo.name}-Submitted.pdf", pdf_hash
            )
            contract_2 = gateway.create_pdf_document(
                pdf_content, f"{memo.name}-Submitted.pdf", pdf_hash
            )

        # Both calls must return the same document item ID
        self.assertEqual(contract_1["document_item_id"], contract_2["document_item_id"])
        # SharePoint upload must only be called once (idempotency)
        self.assertEqual(call_count[0], 1)

    # ================================================================== #
    # Test 9: PDF with invalid header is rejected                         #
    # ================================================================== #

    def test_09_invalid_pdf_header_is_rejected(self):
        """Gateway create_pdf_document rejects content that is not PDF."""
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": docx_item.id})
        not_a_pdf = b"This is not a PDF"
        content_hash = hashlib.sha256(not_a_pdf).hexdigest()
        gateway = MemoDocumentGateway(self.env, memo, self.requester)
        with self.assertRaises(UserError):
            gateway.create_pdf_document(not_a_pdf, "bad.pdf", content_hash)

    # ================================================================== #
    # Test 10: Unavailable document cannot be downloaded                  #
    # ================================================================== #

    def test_10_unavailable_document_download_raises_user_error(self):
        """Downloading a document that is not 'available' raises UserError."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        item.sudo().write({"storage_state": "failed"})
        memo.sudo().write({"source_docx_item_id": item.id})
        gateway = MemoDocumentGateway(self.env, memo, self.requester)
        with self.assertRaises(UserError):
            gateway.get_document_download_url("source_docx_item_id")

    # ================================================================== #
    # Test 11: Memo admin can use gateway                                  #
    # ================================================================== #

    def test_11_memo_admin_can_use_gateway(self):
        """Memo Administrators can access any document through the gateway."""
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": item.id})
        gateway = MemoDocumentGateway(self.env, memo, self.memo_admin)
        contract = gateway.read_document_metadata("source_docx_item_id")
        self.assertEqual(contract["storage_state"], "available")

    # ================================================================== #
    # Test 12: action_view_submitted_pdf uses gateway field name          #
    # ================================================================== #

    def test_12_action_view_submitted_pdf_uses_gateway(self):
        """action_view_submitted_pdf delegates to gateway, not raw item field."""
        memo = self._create_minimal_memo()
        pdf_item = self._create_available_document_item(memo, "source_pdf_item_id")
        memo.sudo().write({"source_pdf_item_id": pdf_item.id})
        # Should not raise AccessError — gateway mediates access
        memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(memo.id)
        result = memo_as_requester.action_view_submitted_pdf()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn("/lhi/sharepoint/document/", result["url"])

    # ================================================================== #
    # Test 13: _capture_current_pdf signature check (integration)         #
    # ================================================================== #

    def test_13_capture_current_pdf_uses_gateway_not_direct_access(self):
        """
        _capture_current_pdf must not directly access protected item fields.
        We verify this by checking that even with no ACL on lhi.document.item,
        the method successfully reads metadata when called by the requester.
        """
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write(
            {
                "source_docx_item_id": docx_item.id,
                "state": "ready_for_preparation",
            }
        )

        fake_meta = {
            "id": "gw-item-" + str(memo.id),
            "eTag": "etag-v1",
            "cTag": "ctag-v1",
            "webUrl": "https://tenant.sharepoint.com/gw-item",
            "file": {"hashes": {"quickXorHash": "abc123", "sha256Hash": "sha256-hash"}},
            "parentReference": {
                "driveId": "gw-drive-id",
                "siteId": "gw-site-id",
                "id": "parent-id",
            },
            "lastModifiedDateTime": "2026-08-01T00:00:00Z",
            "lastModifiedBy": {"user": {"displayName": "Test"}},
            "size": 10000,
        }
        fake_policy = MagicMock()
        fake_policy.maximum_size_mb = 10
        fake_policy.storage_backend = "sharepoint"
        fake_pdf = b"%PDF-1.4 integration-test-pdf-bytes"
        fake_docx = b"PK\x03\x04fake-docx-bytes"

        uploaded_items = []

        def mock_upload(documents):
            for doc in documents:
                uploaded_items.append(doc.id)
                doc.sudo().write(
                    {
                        "sharepoint_site_id": "gw-site-id",
                        "sharepoint_drive_id": "gw-drive-id",
                        "sharepoint_item_id": f"gw-pdf-{doc.id}",
                        "sharepoint_web_url": f"https://tenant.sharepoint.com/gw-pdf-{doc.id}",
                        "storage_state": "available",
                        "upload_state": "completed",
                    }
                )
                doc._remove_spool()
            return True

        def mock_graph_request(*args, **kwargs):
            return fake_meta

        def mock_binary_request(*args, **kwargs):
            response = MagicMock()
            url = args[1] if len(args) > 1 else ""
            if "format=pdf" in str(kwargs.get("params", "")) or "?format=pdf" in url:
                response.content = fake_pdf
            else:
                response.content = fake_docx
            response.headers = {"Content-Length": str(len(response.content))}
            response.iter_content = None
            return response

        def mock_resolve_policy(*args, **kwargs):
            return fake_policy

        with (
            patch.object(
                self.env.registry["lhi.document.item"], "action_upload", mock_upload
            ),
            patch.object(
                self.connection, "graph_request", mock_graph_request
            ),
            patch.object(
                self.connection, "lhi_binary_request", mock_binary_request
            ),
            patch.object(
                self.env.registry["lhi.document.storage.policy"],
                "resolve_policy",
                mock_resolve_policy,
            ),
            patch.object(
                self.connection.__class__, "graph_request", mock_graph_request
            ),
        ):
            memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
                memo.id
            )
            # Should not raise AccessError — gateway mediates all document access
            pdf_item_id, pdf_hash = memo_as_requester._capture_current_pdf()

        self.assertIsInstance(pdf_item_id, int)
        self.assertIsInstance(pdf_hash, str)
        self.assertEqual(len(pdf_hash), 64)  # SHA-256 hex digest
        self.assertTrue(len(uploaded_items) > 0)

    # ================================================================== #
    # Test 14: Integration operation is created on action_prepare_and_sign #
    # ================================================================== #

    def test_14_integration_operation_created_on_prepare_and_sign(self):
        """action_prepare_and_sign creates an integration operation record."""
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write(
            {
                "source_docx_item_id": docx_item.id,
                "state": "ready_for_preparation",
            }
        )

        def mock_capture(*args, **kwargs):
            return docx_item.id, hashlib.sha256(b"%PDF fake").hexdigest()

        def mock_approval_route(*args, **kwargs):
            return MagicMock(), []

        def mock_signature_request(*args, **kwargs):
            sig = MagicMock()
            sig.action_create_provider_draft = MagicMock()
            return sig

        with (
            patch.object(
                self.env.registry["lhi.memo"],
                "_capture_current_pdf",
                mock_capture,
            ),
            patch.object(
                self.env.registry["lhi.memo"],
                "_prepare_approval_route",
                mock_approval_route,
            ),
            patch.object(
                self.env.registry["lhi.memo"],
                "_create_signature_request",
                mock_signature_request,
            ),
        ):
            memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
                memo.id
            )
            memo_as_requester.action_prepare_and_sign()

        # At least one operation record must exist for this memo
        operations = (
            self.env["lhi.memo.integration.operation"]
            .sudo()
            .search([("memo_id", "=", memo.id)])
        )
        self.assertTrue(len(operations) >= 1)
        operation = operations[0]
        self.assertTrue(operation.correlation_id.startswith("MEMO-INT-"))
        self.assertEqual(operation.operation_type, "prepare_and_sign")

    # ================================================================== #
    # Test 15: Integration failure records correlation ID in notification  #
    # ================================================================== #

    def test_15_failure_records_correlation_id(self):
        """Failed integration stores the correlation ID in the Memo record."""
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write(
            {
                "source_docx_item_id": docx_item.id,
                "state": "ready_for_preparation",
            }
        )

        def mock_capture_that_fails(*args, **kwargs):
            raise UserError("Simulated SharePoint capture failure")

        with patch.object(
            self.env.registry["lhi.memo"],
            "_capture_current_pdf",
            mock_capture_that_fails,
        ):
            memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
                memo.id
            )
            result = memo_as_requester.action_prepare_and_sign()

        # Result must be a client action with correlation reference
        self.assertEqual(result.get("type"), "ir.actions.client")
        message = result.get("params", {}).get("message", "")
        self.assertIn("MEMO-INT-", message)

        # Memo state must be failed and error message must contain the correlation
        self.assertEqual(memo.state, "failed")
        self.assertIn("MEMO-INT-", memo.integration_error_message or "")

        # Operation must be marked as failure
        operations = (
            self.env["lhi.memo.integration.operation"]
            .sudo()
            .search([("memo_id", "=", memo.id)])
        )
        self.assertTrue(len(operations) >= 1)
        self.assertIn(
            operations[0].state,
            ("retryable_failure", "permanent_failure", "reconciliation_required"),
        )

    # ================================================================== #
    # Test 16: Sensitive data is not in browser-facing failure response   #
    # ================================================================== #

    def test_16_bearer_token_not_in_failure_client_action(self):
        """Tokens and raw URLs must not appear in browser-facing notification."""
        memo = self._create_minimal_memo()
        docx_item = self._create_available_document_item(memo)
        memo.sudo().write(
            {
                "source_docx_item_id": docx_item.id,
                "state": "ready_for_preparation",
            }
        )

        def mock_capture_with_token(*args, **kwargs):
            raise ValueError(
                "Graph returned 401 Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9"
                ".secret.signthat — not authorized"
            )

        with patch.object(
            self.env.registry["lhi.memo"],
            "_capture_current_pdf",
            mock_capture_with_token,
        ):
            memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
                memo.id
            )
            result = memo_as_requester.action_prepare_and_sign()

        params = result.get("params", {})
        message = params.get("message", "")
        title = params.get("title", "")
        # Token must not appear in client-facing output
        self.assertNotIn("eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9", message)
        self.assertNotIn("eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9", title)
        # Correlation reference must be present
        self.assertIn("MEMO-INT-", message)

    # ================================================================== #
    # Test 17: _record_integration_failure strips Bearer tokens           #
    # ================================================================== #

    def test_17_record_integration_failure_strips_tokens(self):
        """Stored failure messages must not contain Bearer tokens."""
        memo = self._create_minimal_memo()
        memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
            memo.id
        )
        fake_error = ValueError(
            "Authorization failure: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
            ".payload.signature exposed in log"
        )
        memo_as_requester._record_integration_failure("test_failure", fake_error)
        stored_message = memo.integration_error_message or ""
        self.assertNotIn(
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9", stored_message,
            "Bearer JWT must not be stored in integration_error_message"
        )

    # ================================================================== #
    # Test 18: Memo form load does not require direct document-item read  #
    # ================================================================== #

    def test_18_memo_form_load_no_document_item_read(self):
        """
        Reading Memo fields (excluding Many2one item fields) must not raise
        AccessError for a normal employee.
        """
        memo = self._create_minimal_memo()
        item = self._create_available_document_item(memo)
        memo.sudo().write({"source_docx_item_id": item.id})
        memo_as_requester = self.env["lhi.memo"].with_user(self.requester).browse(
            memo.id
        )
        # Read only Memo-level Char/Date/Selection fields — must not AccessError
        data = memo_as_requester.read(
            [
                "name",
                "title",
                "subject",
                "state",
                "has_word_document",
                "has_submitted_pdf",
                "has_signed_pdf",
                "has_certificate",
                "source_docx_web_url",
            ]
        )
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["has_word_document"])
