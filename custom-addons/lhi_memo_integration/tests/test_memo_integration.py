import hashlib
from unittest.mock import patch, MagicMock

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMemoIntegrationOrchestration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.memo_privilege = cls.env.ref("lhi_memo_management.privilege_lhi_memo")
        cls.approver_group = cls.env["res.groups"].create(
            {
                "name": "Orchestration Approver Group",
                "privilege_id": cls.memo_privilege.id,
            }
        )
        cls.department = cls.env["lhi.department"].create(
            {
                "name": "Orchestration Dept",
                "code": "ORCH-DEPT",
                "company_id": cls.company.id,
            }
        )
        cls.requester = cls.env["res.users"].create(
            {
                "name": "Orchestration Requester",
                "login": "orch_requester",
                "email": "orch_req@example.test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "entra_object_id": "req-oid-1111",
                "entra_tenant_id": "tenant-id-aaaa",
                "entra_upn": "orch_req@example.test",
                "lhi_department_ids": [(6, 0, [cls.department.id])],
                "groups_id": [(6, 0, [cls.env.ref("lhi_security.group_lhi_employee").id, cls.env.ref("lhi_security.group_lhi_user").id])],
            }
        )
        cls.approver = cls.env["res.users"].create(
            {
                "name": "Orchestration Approver",
                "login": "orch_approver",
                "email": "orch_app@example.test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "entra_object_id": "app-oid-2222",
                "entra_tenant_id": "tenant-id-aaaa",
                "entra_upn": "orch_app@example.test",
                "lhi_department_ids": [(6, 0, [cls.department.id])],
                "groups_id": [(6, 0, [cls.env.ref("lhi_security.group_lhi_employee").id, cls.env.ref("lhi_security.group_lhi_user").id, cls.approver_group.id])],
            }
        )
        cls.matrix = cls.env["lhi.approval.matrix"].create(
            {
                "name": "Orchestration Matrix",
                "document_type": "memo",
                "company_id": cls.company.id,
                "currency_id": cls.company.currency_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Department Review",
                            "sequence": 10,
                            "approver_group_id": cls.approver_group.id,
                            "approver_ids": [(6, 0, [cls.approver.id])],
                            "approval_type": "any",
                        },
                    )
                ],
            }
        )
        cls.category = cls.env["lhi.memo.category"].create(
            {
                "name": "Orchestration Category",
                "code": "ORCH-CAT",
                "approval_matrix_id": cls.matrix.id,
                "final_signature_required": False,
                "requester_signature_required": True,
            }
        )
        cls.connection = cls.env["lhi.graph.connection"].create(
            {
                "name": "Orchestration Graph Connection",
                "company_id": cls.company.id,
                "tenant_id": "tenant-id-aaaa",
                "client_id": "client-id-bbbb",
                "client_secret": "secret",
                "auth_state": "authenticated",
            }
        )
        cls.docx_item = cls.env["lhi.document.item"].create(
            {
                "name": "Template.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "file_size": 1024,
                "storage_state": "available",
                "upload_state": "completed",
                "company_id": cls.company.id,
                "graph_connection_id": cls.connection.id,
                "sharepoint_drive_id": "drive-123",
                "sharepoint_item_id": "item-123",
            }
        )
        cls.policy = cls.env["lhi.document.storage.policy"].create(
            {
                "name": "Memo Policy",
                "model_name": "lhi.memo",
                "field_name": "source_docx_item_id",
                "company_id": cls.company.id,
                "maximum_size_mb": 25,
            }
        )
        cls.opensign_config = cls.env["lhi.opensign.configuration"].create(
            {
                "name": "OpenSign Config",
                "company_id": cls.company.id,
                "base_url": "https://sign.example.test",
                "api_token": "token-xyz",
                "active": True,
            }
        )

    def _create_memo(self):
        return self.env["lhi.memo"].with_user(self.requester).create(
            {
                "title": "Test Integration Memo",
                "memo_category_id": self.category.id,
                "requester_id": self.requester.id,
                "department_id": self.department.id,
                "source_docx_item_id": self.docx_item.id,
                "amount": 100.0,
                "currency_id": self.company.currency_id.id,
                "company_id": self.company.id,
            }
        )

    def test_contract_validation(self):
        res = self.env["lhi.memo.integration.contracts"].validate_all_contracts()
        self.assertTrue(res)

    def test_integration_operations_menu_is_under_memo_configuration(self):
        integration_menu = self.env.ref(
            "lhi_memo_integration.menu_memo_integration_operations"
        )
        configuration_menu = self.env.ref(
            "lhi_memo_management.menu_lhi_memo_configuration"
        )
        self.assertEqual(integration_menu.parent_id, configuration_menu)

    def test_preflight_success(self):
        memo = self._create_memo()
        preflight_res = memo.action_preflight_prepare_and_sign()
        self.assertTrue(preflight_res)

    def test_preflight_missing_approval_matrix(self):
        memo = self._create_memo()
        memo.memo_category_id.write({"approval_matrix_id": False})
        with patch.object(self.env["lhi.approval.matrix"], "find_matching_matrix", return_value=self.env["lhi.approval.matrix"]):
            with self.assertRaises(UserError):
                memo.action_preflight_prepare_and_sign()

    def test_preflight_unlinked_entra_identity(self):
        memo = self._create_memo()
        unlinked_user = self.env["res.users"].create(
            {
                "name": "Unlinked User",
                "login": "unlinked_user",
                "email": "unlinked@example.test",
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.matrix.line_ids[0].write({"approver_ids": [(6, 0, [unlinked_user.id])]})
        with self.assertRaises((UserError, ValidationError)):
            memo.action_preflight_prepare_and_sign()

    def test_prepare_and_sign_idempotency(self):
        memo = self._create_memo()
        mock_pdf_item = self.docx_item
        mock_pdf_hash = "abc123hash"
        mock_storage_res = {
            "contract_version": 1,
            "document_item_id": mock_pdf_item.id,
            "storage_state": "available",
            "content_hash": mock_pdf_hash,
            "version": "1.0",
        }
        mock_sig_req = self.env["lhi.opensign.request"].create(
            {
                "res_model": memo._name,
                "res_id": memo.id,
                "company_id": self.company.id,
                "configuration_id": self.opensign_config.id,
                "provider_request_id": "prov-req-999",
                "provider_preparation_url": "https://sign.example.test/prep/999",
            }
        )
        mock_sig_res = {
            "contract_version": 1,
            "signature_request_id": mock_sig_req.id,
            "provider_request_id": "prov-req-999",
            "preparation_url": "https://sign.example.test/prep/999",
            "outcome": "confirmed",
        }

        with patch.object(self.env["lhi.document.item"], "_lhi_prepare_and_confirm_memo_document", return_value=mock_storage_res), \
             patch.object(self.env["lhi.opensign.request"], "_lhi_create_memo_signature_draft", return_value=mock_sig_res), \
             patch.object(memo, "_create_signature_request", return_value=mock_sig_req):
            res1 = memo.action_prepare_and_sign()
            self.assertEqual(res1.get("type"), "ir.actions.act_url")
            op = memo.current_operation_id
            self.assertTrue(op)
            self.assertEqual(op.state, "completed")

            # Second call must hit idempotency memory and return same URL
            res2 = memo.action_prepare_and_sign()
            self.assertEqual(res2.get("type"), "ir.actions.act_url")
            self.assertEqual(memo.current_operation_id, op)

    def test_retry_resumes_from_failed_operation(self):
        memo = self._create_memo()
        op = self.env["lhi.memo.integration.operation"].sudo().create(
            {
                "memo_id": memo.id,
                "operation_type": "prepare_and_sign",
                "state": "retryable_failure",
                "current_step": "generating_pdf",
                "failure_code": "network_error",
                "safe_failure_message": "Temporary connection timeout",
                "requested_by": self.requester.id,
            }
        )
        memo.sudo().write({"current_operation_id": op.id})
        with patch.object(memo, "action_prepare_and_sign") as mock_prep:
            memo.action_retry_integration()
            self.assertEqual(op.state, "draft")
            self.assertEqual(op.retry_count, 1)
            mock_prep.assert_called_once()
