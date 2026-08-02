import hashlib
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.lhi_memo_management.services.memo_document_gateway import MemoDocumentGateway

_logger = logging.getLogger(__name__)


class LhiMemoIntegration(models.Model):
    """
    Extends lhi.memo with saga operation tracking, preflight validation,
    PDF capture, and end-to-end integration orchestration.

    Owned exclusively by ``lhi_memo_integration``. This module provides the
    sole effective implementation of ``action_prepare_and_sign``,
    ``action_continue_preparation``, ``action_retry_integration``, and
    ``action_reconcile_integration``.
    """

    _inherit = "lhi.memo"

    integration_operation_ids = fields.One2many(
        "lhi.memo.integration.operation",
        "memo_id",
        string="Integration Operations",
    )
    current_operation_id = fields.Many2one(
        "lhi.memo.integration.operation",
        string="Current Integration Operation",
        copy=False,
    )
    integration_operation_id = fields.Many2one(
        "lhi.memo.integration.operation",
        string="Integration Operation",
        related="current_operation_id",
        store=True,
    )
    integration_correlation_id = fields.Char(
        string="Integration Correlation ID",
        related="current_operation_id.correlation_id",
        store=True,
    )
    integration_correlation_ref = fields.Char(
        string="Integration Correlation Ref",
        compute="_compute_integration_correlation_ref",
    )
    current_integration_step = fields.Char(
        string="Current Integration Step",
        related="current_operation_id.current_step",
    )
    integration_retry_count = fields.Integer(
        string="Integration Retry Count",
        related="current_operation_id.retry_count",
    )
    outcome_uncertain = fields.Boolean(
        string="Outcome Uncertain",
        related="current_operation_id.outcome_uncertain",
    )
    requires_reconciliation = fields.Boolean(
        string="Requires Reconciliation",
        related="current_operation_id.requires_reconciliation",
    )

    @api.depends("current_operation_id.name", "current_operation_id.correlation_id")
    def _compute_integration_correlation_ref(self):
        for memo in self:
            op = memo.current_operation_id
            memo.integration_correlation_ref = op.name if op else False

    def _generate_correlation_id(self):
        """Generate a safe, opaque correlation reference for end users."""
        self.ensure_one()
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        suffix = str(uuid.uuid4()).replace("-", "")[:8].upper()
        return f"MEMO-INT-{date_part}-{suffix}"

    def action_preflight_prepare_and_sign(self):
        """
        Preflight stage: validates all prerequisites before making external
        writes or API calls.
        """
        self.ensure_one()
        if hasattr(self.env.get("lhi.memo.integration.contracts"), "validate_all_contracts"):
            self.env["lhi.memo.integration.contracts"].validate_all_contracts()

        # 1. Requester authorization
        self._ensure_requester_or_preparer()

        # 2. Category active
        category = self.memo_category_id
        if not category or not category.active:
            raise UserError(_("The selected Memo category is inactive or missing."))

        # 3. Approval matrix match
        matrix_result = self.env["lhi.approval.matrix"]._lhi_get_memo_approval_route(
            self,
            amount=self.amount,
            currency=self.currency_id,
            department=self.department_id,
            office=self.office_id,
            award=self.grant_id,
            project=self.project_id,
        )
        if not matrix_result.get("stages"):
            raise UserError(
                _(
                    "No active approval matrix matches this Memo category, "
                    "amount, and organizational context."
                )
            )

        # 4. Approvers check
        for stage in matrix_result["stages"]:
            approver_user_ids = stage.get("approver_user_ids") or []
            if not approver_user_ids:
                raise UserError(
                    _("Approval stage '%s' has no eligible active approver.") % stage["name"]
                )
            if stage.get("approval_type") == "any" and len(approver_user_ids) != 1:
                raise UserError(
                    _("Memo stage '%s' must resolve to exactly one approver.") % stage["name"]
                )

        # 5. Participants check & Entra identity resolution
        requester_identity = self.requester_id._lhi_get_memo_identity_contract()
        if not requester_identity.get("entra_object_id"):
            raise UserError(
                _("Requester %s does not have a synchronized Entra identity.")
                % self.requester_id.display_name
            )

        participant_users = self.env["res.users"].browse()
        for stage in matrix_result["stages"]:
            participant_users |= self.env["res.users"].browse(stage["approver_user_ids"])

        for participant_user in participant_users:
            if not participant_user.active:
                raise UserError(
                    _("Memo participant %s is inactive.") % participant_user.display_name
                )
            if self.company_id not in participant_user.company_ids:
                raise UserError(
                    _("Memo participant %s is not authorized for company %s.")
                    % (participant_user.display_name, self.company_id.display_name)
                )
            participant_identity = participant_user._lhi_get_memo_identity_contract()
            if not participant_identity.get("entra_object_id"):
                raise UserError(
                    _("Participant %s does not have a synchronized Entra identity.")
                    % participant_user.display_name
                )

        # 6. Template & SharePoint DOCX item check
        sudo_self = self.sudo()
        if not sudo_self.source_docx_item_id:
            raise UserError(
                _("The Word document template is missing or not confirmed in SharePoint.")
            )
        if sudo_self.source_docx_item_id.storage_state != "available":
            raise UserError(
                _("The Word document template is missing or not confirmed in SharePoint.")
            )

        # 7. SharePoint storage policy
        policy = (
            self.env["lhi.document.storage.policy"]
            .sudo()
            .resolve_policy(self._name, "source_docx_item_id", self.company_id)
        )
        if not policy:
            raise UserError(_("No active SharePoint storage policy exists for memos."))

        # 8. LHI Sign configuration check
        sign_config = self.env["lhi.opensign.configuration"]._get_for_company(
            company=self.company_id, required=False
        )
        if not sign_config or not sign_config.active:
            raise UserError(
                _("No active LHI Sign configuration exists for %s.")
                % self.company_id.display_name
            )

        return True

    def _compute_idempotency_key(self, operation_type="prepare_and_sign"):
        self.ensure_one()
        raw = (
            f"memo|{self.id}|{self.source_docx_version_id or self.write_date}"
            f"|{self.amount}|{self.currency_id.id}|{operation_type}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _capture_current_pdf(self, *, retry_failed=False, operation=None):
        """
        Capture the current DOCX as a PDF via the MemoDocumentGateway.
        """
        self.ensure_one()
        gateway = MemoDocumentGateway(self.env, self, self.env.user)

        if operation:
            operation._transition_step("reading_source_document", "reading_source_document")

        docx_meta = gateway.read_document_metadata("source_docx_item_id")
        if docx_meta["storage_state"] != "available":
            raise UserError(_("The Word document is not confirmed in SharePoint."))

        connection = (
            self.env["lhi.graph.connection"]
            .sudo()
            .browse(docx_meta["connection_id"])
        )
        drive_id = docx_meta["drive_id"]
        item_id_sp = docx_meta["item_id"]
        resource = f"/drives/{quote(drive_id)}/items/{quote(item_id_sp)}"

        metadata = connection.graph_request(
            "GET",
            resource,
            auth_context="application",
            params={
                "$select": "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,lastModifiedBy,parentReference,file"
            },
        )
        if metadata.get("id") != item_id_sp:
            raise UserError(_("SharePoint returned a different Word DriveItem."))

        policy = (
            self.env["lhi.document.storage.policy"]
            .sudo()
            .resolve_policy(self._name, "source_docx_item_id", self.company_id)
        )
        if not policy:
            raise UserError(_("No SharePoint storage policy is configured for memos."))
        maximum_bytes = policy.maximum_size_mb * 1024 * 1024

        if operation:
            operation._transition_step("capturing_pdf", "capturing_pdf")

        docx_response = connection.lhi_binary_request(
            "GET",
            f"{resource}/content",
            auth_context="application",
            expected_statuses={200},
            stream=True,
        )
        docx_content = self._bounded_response_content(docx_response, maximum_bytes)
        if not docx_content:
            raise UserError(_("SharePoint returned an empty Word document."))

        pdf_response = connection.lhi_binary_request(
            "GET",
            f"{resource}/content?format=pdf",
            auth_context="application",
            expected_statuses={200},
            stream=True,
        )
        pdf_content = self._bounded_response_content(pdf_response, maximum_bytes)

        metadata_after = connection.graph_request(
            "GET",
            resource,
            auth_context="application",
            params={
                "$select": "id,size,eTag,cTag,webUrl,lastModifiedDateTime,lastModifiedBy,parentReference,file"
            },
        )
        version = metadata.get("cTag") or metadata.get("eTag")
        version_after = metadata_after.get("cTag") or metadata_after.get("eTag")
        if version != version_after or metadata.get("eTag") != metadata_after.get("eTag"):
            raise UserError(
                _("The Word document changed during PDF capture. Save it and retry.")
            )
        if not pdf_content.startswith(b"%PDF"):
            raise UserError(_("Microsoft 365 did not return a valid PDF conversion."))

        gateway.update_docx_checksums(
            "source_docx_item_id",
            len(docx_content),
            hashlib.sha256(docx_content).hexdigest(),
            hashlib.sha1(docx_content).hexdigest(),
        )
        gateway.apply_drive_item_metadata("source_docx_item_id", metadata_after)

        pdf_hash = hashlib.sha256(pdf_content).hexdigest()
        if self.state == "returned" and self.signature_request_ids.filtered(
            lambda request: request.source_pdf_hash == pdf_hash
        ):
            raise UserError(
                _(
                    "The returned memo has not changed. Save a corrected Word version first."
                )
            )

        if operation:
            operation._transition_step("confirming_pdf", "confirming_pdf")

        filename = f"{self._safe_filename(self.name)}-Submitted.pdf"
        pdf_contract = gateway.create_pdf_document(pdf_content, filename, pdf_hash)
        pdf_item_id = pdf_contract["document_item_id"]

        self.sudo().write(
            {
                "source_docx_version_id": version,
                "source_docx_etag": metadata.get("eTag"),
                "source_docx_web_url": metadata_after.get("webUrl") or self.source_docx_web_url,
                "source_pdf_item_id": pdf_item_id,
                "source_pdf_hash": pdf_hash,
            }
        )
        return pdf_item_id, pdf_hash

    def action_prepare_and_sign(self):
        """
        Orchestrates Prepare and Sign as an idempotent saga operation.
        """
        self.ensure_one()
        self._prepare_and_sign_precheck()

        correlation_id = self._generate_correlation_id()
        idempotency_key = self._compute_idempotency_key("prepare_and_sign")

        existing_op = (
            self.env["lhi.memo.integration.operation"]
            .sudo()
            .search([("idempotency_key", "=", idempotency_key)], limit=1)
        )

        if existing_op:
            if existing_op.state == "completed" and self.signature_request_id.provider_preparation_url:
                return {
                    "type": "ir.actions.act_url",
                    "url": f"/lhi/memo/{self.uuid}/prepare",
                    "target": "new",
                }
            if existing_op.requires_reconciliation:
                raise UserError(
                    _("Memo operation %s requires administrator reconciliation before retrying.")
                    % existing_op.name
                )
            operation = existing_op
        else:
            operation = (
                self.env["lhi.memo.integration.operation"]
                .sudo()
                .create(
                    {
                        "memo_id": self.id,
                        "operation_type": "prepare_and_sign",
                        "correlation_id": correlation_id,
                        "idempotency_key": idempotency_key,
                        "state": "draft",
                        "current_step": "draft",
                        "requested_by_id": self.env.user.id,
                        "started_at": fields.Datetime.now(),
                    }
                )
            )

        self.sudo().write({"current_operation_id": operation.id})

        try:
            # Step 1: Preflight
            operation._transition_step("validating", "validating")
            self.action_preflight_prepare_and_sign()

            # Step 2: Document Conversion & SharePoint Storage
            pdf_item_id, pdf_hash = self._capture_current_pdf(
                retry_failed=self.state == "failed",
                operation=operation,
            )
            pdf_item = self.env["lhi.document.item"].sudo().browse(pdf_item_id)

            # Step 3: Route Resolution
            operation._transition_step("preparing_approval_route", "preparing_approval_route")
            _approval_request, approval_lines = self._prepare_approval_route()

            # Step 4: Signature Request Creation
            operation._transition_step("creating_signature_request", "creating_signature_request")
            signature_request = self._create_signature_request(
                approval_lines, pdf_item, pdf_hash
            )

            if self.state != "preparing":
                self._transition("preparing")

            # Step 5: Provider Draft Creation
            operation._transition_step("creating_provider_draft", "creating_provider_draft")
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            redirect_url = f"{base_url}/web#id={self.id}&model=lhi.memo&view_type=form"

            if hasattr(self.env["lhi.opensign.request"], "_lhi_create_memo_signature_draft"):
                self.env["lhi.opensign.request"]._lhi_create_memo_signature_draft(
                    signature_request, redirect_url
                )
            elif hasattr(signature_request.sudo(), "action_create_provider_draft"):
                signature_request.sudo().action_create_provider_draft(
                    redirect_url=redirect_url
                )

            operation._transition_step("awaiting_requester_signature", "completed")
            self._notify_users(
                self.requester_id,
                _("Requester signature required"),
                _("Prepare the fields for memo %s, then sign and submit it.") % self.name,
                schedule_activity=True,
            )

            return {
                "type": "ir.actions.act_url",
                "url": f"/lhi/memo/{self.uuid}/prepare",
                "target": "new",
            }

        except UserError as user_err:
            operation._mark_failed("configuration_failure", user_err, failure_type="permanent")
            return self._record_integration_failure(
                "memo_preparation", user_err, correlation_id=correlation_id
            )
        except AccessError as access_err:
            operation._mark_failed("access_denied", access_err, failure_type="permanent")
            return self._record_integration_failure(
                "memo_preparation", access_err, correlation_id=correlation_id
            )
        except Exception as general_err:
            _logger.exception("Memo %s integration failure: %s", self.name, str(general_err))
            operation._mark_failed("integration_error", general_err, failure_type="retryable")
            return self._record_integration_failure(
                "memo_preparation", general_err, correlation_id=correlation_id
            )

    def action_continue_preparation(self):
        self.ensure_one()
        self._ensure_requester_or_preparer()
        if not self.signature_request_id.provider_preparation_url:
            raise UserError(_("No secure preparation URL is available."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/lhi/memo/{self.uuid}/prepare",
            "target": "new",
        }

    def action_retry_integration(self):
        self.ensure_one()
        if self.current_operation_id:
            return self.current_operation_id.action_retry()
        return self.action_prepare_and_sign()

    def action_reconcile_integration(self):
        self.ensure_one()
        if self.current_operation_id:
            return self.current_operation_id.action_reconcile()
        raise UserError(_("No active operation to reconcile."))
