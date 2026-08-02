import logging
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

OPERATION_STATES = [
    ("draft", "Draft"),
    ("validating", "Validating Preflight"),
    ("reading_source_document", "Reading Source Document"),
    ("capturing_pdf", "Capturing PDF Conversion"),
    ("confirming_pdf", "Confirming PDF Document in SharePoint"),
    ("preparing_approval_route", "Preparing Approval Route"),
    ("creating_signature_request", "Creating Signature Request"),
    ("creating_provider_draft", "Creating Provider Draft"),
    ("awaiting_requester_signature", "Awaiting Requester Signature"),
    ("completed", "Completed"),
    ("retryable_failure", "Retryable Failure"),
    ("reconciliation_required", "Reconciliation Required"),
    ("permanent_failure", "Permanent Failure"),
    ("cancelled", "Cancelled"),
]

OPERATION_TYPES = [
    ("prepare_and_sign", "Prepare and Sign"),
    ("submit_and_sign", "Submit and Sign"),
    ("approve_and_sign", "Approve and Sign"),
    ("retry", "Retry Integration"),
    ("reconcile", "Reconcile Integration"),
]


class LhiMemoIntegrationOperation(models.Model):
    """
    Durable saga record for a single Memo integration operation.

    Owned exclusively by ``lhi_memo_integration``. Tracks correlation ID,
    step progression, failure classification, idempotency keys, and
    reconciliation state.
    """

    _name = "lhi.memo.integration.operation"
    _description = "LHI Memo Integration Saga Operation"
    _order = "started_at desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Operation Reference",
        required=True,
        copy=False,
        default="New",
        index=True,
    )
    memo_id = fields.Many2one(
        "lhi.memo",
        string="Memo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="memo_id.company_id",
        store=True,
        index=True,
    )
    correlation_id = fields.Char(
        string="Correlation ID",
        required=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        index=True,
    )
    idempotency_key = fields.Char(
        string="Idempotency Key",
        copy=False,
        index=True,
    )
    operation_type = fields.Selection(
        OPERATION_TYPES,
        string="Operation Type",
        required=True,
        default="prepare_and_sign",
    )
    state = fields.Selection(
        OPERATION_STATES,
        string="Operation State",
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    current_step = fields.Char(
        string="Current Step",
        default="draft",
    )
    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
    )
    requested_by = fields.Many2one(
        "res.users",
        related="requested_by_id",
        string="Requested By (Alias)",
    )
    started_at = fields.Datetime(
        string="Started At",
        default=fields.Datetime.now,
        required=True,
    )
    completed_at = fields.Datetime(
        string="Completed At",
        copy=False,
    )
    retry_count = fields.Integer(
        string="Retry Count",
        default=0,
    )
    failure_code = fields.Char(
        string="Failure Code",
        copy=False,
    )
    safe_failure_message = fields.Text(
        string="Safe Failure Message",
        copy=False,
    )
    technical_failure_reference = fields.Text(
        string="Technical Failure Reference",
        copy=False,
    )
    outcome_uncertain = fields.Boolean(
        string="Outcome Uncertain",
        default=False,
    )
    requires_reconciliation = fields.Boolean(
        string="Requires Reconciliation",
        default=False,
    )
    approval_route_snapshot_hash = fields.Char(
        string="Approval Route Snapshot Hash",
    )
    source_document_hash = fields.Char(
        string="Source Document Hash",
    )
    signature_route_hash = fields.Char(
        string="Signature Route Hash",
    )

    _idempotency_key_unique = models.Constraint(
        "unique(idempotency_key)",
        "The integration operation idempotency key must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                date_str = fields.Date.context_today(self).strftime("%Y%m%d")
                seq = (
                    self.env["ir.sequence"].next_by_code(
                        "lhi.memo.integration.operation"
                    )
                    or str(uuid.uuid4())[:8].upper()
                )
                vals["name"] = f"MEMO-INT-{date_str}-{seq}"
        return super().create(vals_list)

    def _transition_step(self, step_name, new_state=None):
        self.ensure_one()
        vals = {"current_step": step_name}
        if new_state:
            vals["state"] = new_state
        if new_state == "completed":
            vals["completed_at"] = fields.Datetime.now()
            vals["requires_reconciliation"] = False
            vals["outcome_uncertain"] = False
        self.sudo().write(vals)
        _logger.info(
            "Memo Operation %s [%s] transitioned step to %s (state: %s)",
            self.name,
            self.correlation_id,
            step_name,
            new_state or self.state,
        )

    def _advance_step(self, step_name):
        self._transition_step(step_name, step_name)

    def _complete(self):
        self._transition_step("completed", "completed")

    def _mark_failed(self, code, error, failure_type="retryable"):
        self.ensure_one()
        safe_msg = self._safe_error_text(str(error))
        tech_ref = self.correlation_id

        if failure_type == "reconciliation":
            state = "reconciliation_required"
            outcome_uncertain = True
            requires_reconciliation = True
        elif failure_type == "permanent":
            state = "permanent_failure"
            outcome_uncertain = False
            requires_reconciliation = False
        else:
            state = "retryable_failure"
            outcome_uncertain = False
            requires_reconciliation = False

        self.sudo().write(
            {
                "state": state,
                "failure_code": code,
                "safe_failure_message": safe_msg[:500],
                "technical_failure_reference": tech_ref,
                "outcome_uncertain": outcome_uncertain,
                "requires_reconciliation": requires_reconciliation,
                "completed_at": fields.Datetime.now(),
            }
        )
        _logger.warning(
            "Memo Operation %s [%s] failed at step %s with code %s: %s",
            self.name,
            self.correlation_id,
            self.current_step,
            code,
            safe_msg,
        )

    def _fail(self, error):
        self._mark_failed("integration_error", error, failure_type="retryable")

    @staticmethod
    def _safe_error_text(error_text):
        import re

        cleaned = re.sub(
            r"Bearer [A-Za-z0-9._\-+/=]{20,}", "[REDACTED_TOKEN]", error_text
        )
        cleaned = re.sub(r"https?://[^\s'\"]{40,}", "[REDACTED_URL]", cleaned)
        return cleaned[:500]

    def action_retry(self):
        self.ensure_one()
        if self.state not in ("retryable_failure", "permanent_failure"):
            raise UserError(_("Only failed operations can be retried."))
        if self.requires_reconciliation:
            raise UserError(
                _(
                    "This operation requires administrator reconciliation before retry."
                )
            )
        self.sudo().write(
            {
                "retry_count": self.retry_count + 1,
                "state": "draft",
                "failure_code": False,
                "safe_failure_message": False,
                "technical_failure_reference": False,
            }
        )
        return self.memo_id.action_prepare_and_sign()

    def action_reconcile(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            raise AccessError(
                _("Only ERP Administrators may reconcile integration operations.")
            )
        memo = self.memo_id
        if memo.signature_request_id and memo.signature_request_id.provider_request_id:
            memo.signature_request_id.action_reconcile()
            if memo.signature_request_id.provider_preparation_url:
                self.sudo().write(
                    {
                        "state": "awaiting_requester_signature",
                        "outcome_uncertain": False,
                        "requires_reconciliation": False,
                    }
                )
                memo.sudo().write({"state": "preparing"})
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Reconciliation Successful"),
                        "message": _(
                            "Provider signature request was reconciled and confirmed."
                        ),
                        "type": "success",
                    },
                }
        self.sudo().write(
            {
                "state": "retryable_failure",
                "outcome_uncertain": False,
                "requires_reconciliation": False,
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reconciliation Completed"),
                "message": _("Operation reset for retry."),
                "type": "warning",
            },
        }
