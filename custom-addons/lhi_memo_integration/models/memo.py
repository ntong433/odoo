import hashlib
import logging
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class LhiMemoIntegration(models.Model):
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
    integration_correlation_ref = fields.Char(
        string="Integration Correlation Ref",
        compute="_compute_integration_correlation_ref",
    )

    @api.depends("current_operation_id.name", "current_operation_id.correlation_id")
    def _compute_integration_correlation_ref(self):
        for memo in self:
            op = memo.current_operation_id
            memo.integration_correlation_ref = op.name if op else False

    def action_preflight_prepare_and_sign(self):
        """Preflight stage: validates all prerequisites before making external writes or API calls."""
        self.ensure_one()
        # Validate contract compatibility first
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
                _("No active approval matrix matches this Memo category, amount, and organizational context.")
            )

        # 4. Approvers check
        for stage in matrix_result["stages"]:
            user_ids = stage.get("approver_user_ids") or []
            if not user_ids:
                raise UserError(
                    _("Approval stage '%s' has no eligible active approver.") % stage["name"]
                )
            if stage.get("approval_type") == "any" and len(user_ids) != 1:
                raise UserError(
                    _("Memo stage '%s' must resolve to exactly one approver.") % stage["name"]
                )

        # 5. Participants check & Entra identity resolution
        requester_identity = self.requester_id._lhi_get_memo_identity_contract()
        if not requester_identity.get("entra_object_id"):
            raise UserError(
                _("Requester %s does not have a synchronized Entra identity.") % self.requester_id.display_name
            )

        participant_users = self.env["res.users"].browse()
        for stage in matrix_result["stages"]:
            participant_users |= self.env["res.users"].browse(stage["approver_user_ids"])

        for p_user in participant_users:
            if not p_user.active:
                raise UserError(_("Memo participant %s is inactive.") % p_user.display_name)
            if self.company_id not in p_user.company_ids:
                raise UserError(
                    _("Memo participant %s is not authorized for company %s.")
                    % (p_user.display_name, self.company_id.display_name)
                )
            p_identity = p_user._lhi_get_memo_identity_contract()
            if not p_identity.get("entra_object_id"):
                raise UserError(
                    _("Participant %s does not have a synchronized Entra identity.") % p_user.display_name
                )

        # 6. Template & SharePoint DOCX item check
        if not self.source_docx_item_id or self.source_docx_item_id.storage_state != "available":
            raise UserError(_("The Word document template is missing or not confirmed in SharePoint."))

        # 7. SharePoint storage policy
        policy = self.env["lhi.document.storage.policy"].resolve_policy(
            self._name, "source_docx_item_id", self.company_id
        )
        if not policy:
            raise UserError(_("No active SharePoint storage policy exists for memos."))

        # 8. LHI Sign configuration check
        config = self.env["lhi.opensign.configuration"]._get_for_company(
            company=self.company_id, required=False
        )
        if not config or not config.active:
            raise UserError(
                _("No active LHI Sign configuration exists for %s.") % self.company_id.display_name
            )

        return True

    def _compute_idempotency_key(self, operation_type="prepare_and_sign"):
        self.ensure_one()
        raw = f"memo|{self.id}|{self.source_docx_version_id or self.write_date}|{self.amount}|{self.currency_id.id}|{operation_type}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def action_prepare_and_sign(self):
        """Orchestrates Prepare and Sign as an idempotent saga operation."""
        self.ensure_one()

        # Check existing operations for idempotency
        idempotency_key = self._compute_idempotency_key("prepare_and_sign")
        existing_op = self.env["lhi.memo.integration.operation"].sudo().search(
            [("idempotency_key", "=", idempotency_key)], limit=1
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
            operation = self.env["lhi.memo.integration.operation"].sudo().create({
                "memo_id": self.id,
                "operation_type": "prepare_and_sign",
                "idempotency_key": idempotency_key,
                "state": "draft",
                "requested_by": self.env.user.id,
            })

        self.sudo().write({"current_operation_id": operation.id})

        try:
            # Step 1: Preflight
            operation._transition_step("validating", "validating")
            self.action_preflight_prepare_and_sign()

            # Step 2: Route Resolution
            operation._transition_step("preparing_route", "preparing_route")
            approval_request, approval_lines = self._prepare_approval_route()

            # Step 3: Document Conversion & SharePoint Storage
            operation._transition_step("generating_pdf", "generating_pdf")
            policy = self.env["lhi.document.storage.policy"].resolve_policy(
                self._name, "source_docx_item_id", self.company_id
            )
            storage_res = self.env["lhi.document.item"]._lhi_prepare_and_confirm_memo_document(
                self, self.source_docx_item_id, policy
            )
            pdf_item = self.env["lhi.document.item"].browse(storage_res["document_item_id"])
            pdf_hash = storage_res["content_hash"]

            # Step 4: Signature Request Creation
            operation._transition_step("creating_signature_request", "creating_signature_request")
            signature_request = self._create_signature_request(
                approval_lines, pdf_item, pdf_hash
            )

            # Step 5: Provider Draft Creation
            operation._transition_step("creating_provider_draft", "creating_provider_draft")
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            redirect_url = f"{base_url}/web#id={self.id}&model=lhi.memo&view_type=form"

            sig_res = self.env["lhi.opensign.request"]._lhi_create_memo_signature_draft(
                signature_request, redirect_url
            )

            # Mark completed & transition Memo state
            operation._transition_step("awaiting_requester_signature", "completed")
            if self.state != "preparing":
                self._transition("preparing")

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
            return self._format_safe_user_notification(operation, user_err)
        except AccessError as access_err:
            operation._mark_failed("access_denied", access_err, failure_type="permanent")
            return self._format_safe_user_notification(operation, access_err)
        except Exception as general_err:
            _logger.exception("Memo %s integration failure: %s", self.name, str(general_err))
            operation._mark_failed("integration_error", general_err, failure_type="retryable")
            return self._format_safe_user_notification(operation, general_err)

    def _format_safe_user_notification(self, operation, error):
        self.ensure_one()
        safe_msg = _(
            "Memo integration needs attention.\nReference: %s"
        ) % operation.name
        self.sudo().write({
            "state": "failed",
            "integration_error_code": operation.failure_code,
            "integration_error_message": safe_msg,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Memo integration needs attention"),
                "message": safe_msg,
                "type": "warning",
                "sticky": True,
            },
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
