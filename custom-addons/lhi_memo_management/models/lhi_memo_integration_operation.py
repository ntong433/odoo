import uuid as uuid_lib
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class LhiMemoIntegrationOperation(models.Model):
    """
    Durable saga record for a single Memo integration attempt.

    One operation is created per ``action_prepare_and_sign`` invocation.
    It tracks correlation ID, step progression, failure classification,
    idempotency keys, and reconciliation flags.

    Employees have no access to this model.  Memo Administrators and
    ERP Administrators may read and act on operation records.
    """

    _name = "lhi.memo.integration.operation"
    _description = "LHI Memo Integration Operation"
    _order = "started_at desc, id desc"
    _rec_name = "correlation_id"

    memo_id = fields.Many2one(
        "lhi.memo",
        required=True,
        ondelete="cascade",
        index=True,
        string="Memo",
    )
    correlation_id = fields.Char(
        required=True,
        copy=False,
        index=True,
        string="Correlation Reference",
        help="Safe reference shown to end users in failure notifications.",
    )
    operation_type = fields.Selection(
        [
            ("prepare_and_sign", "Prepare and Sign"),
            ("word_document", "Word Document Creation"),
            ("reconcile", "Reconciliation"),
            ("retry", "Retry"),
        ],
        required=True,
        string="Operation",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validating", "Validating"),
            ("reading_source_document", "Reading Source Document"),
            ("capturing_pdf", "Capturing PDF"),
            ("confirming_pdf", "Confirming PDF"),
            ("preparing_approval_route", "Preparing Approval Route"),
            ("creating_signature_request", "Creating Signature Request"),
            ("creating_provider_draft", "Creating Provider Draft"),
            ("completed", "Completed"),
            ("retryable_failure", "Retryable Failure"),
            ("reconciliation_required", "Reconciliation Required"),
            ("permanent_failure", "Permanent Failure"),
        ],
        default="draft",
        required=True,
        tracking=True,
        string="State",
    )
    current_step = fields.Char(
        string="Current Step",
        help="Machine name of the last recorded step.",
    )
    started_at = fields.Datetime(
        string="Started At",
        default=fields.Datetime.now,
        required=True,
    )
    completed_at = fields.Datetime(string="Completed At")
    requested_by_id = fields.Many2one(
        "res.users",
        required=True,
        string="Requested By",
    )
    retry_count = fields.Integer(default=0, string="Retry Count")
    failure_code = fields.Char(string="Failure Code")
    safe_failure_message = fields.Char(
        string="Safe Failure Message",
        help="Message safe to show to end users — no tokens, IDs, or stack traces.",
    )
    technical_failure_reference = fields.Char(
        string="Technical Reference",
        help="Internal log correlation key for administrator diagnostics.",
        groups="lhi_memo_management.group_lhi_memo_admin",
    )
    outcome_uncertain = fields.Boolean(
        default=False,
        string="Outcome Uncertain",
        help="Set when a remote provider call was made but no response was received.",
    )
    requires_reconciliation = fields.Boolean(
        default=False,
        string="Requires Reconciliation",
        help="Set when an admin must verify the remote provider state before retry.",
    )
    idempotency_key = fields.Char(
        copy=False,
        index=True,
        string="Idempotency Key",
        groups="lhi_memo_management.group_lhi_memo_admin",
    )

    # ------------------------------------------------------------------ #
    # Step progression helpers                                            #
    # ------------------------------------------------------------------ #

    def _advance_step(self, step_name):
        """Record that the operation has advanced to ``step_name``."""
        self.ensure_one()
        self.sudo().write({"state": step_name, "current_step": step_name})

    def _complete(self):
        """Mark the operation as successfully completed."""
        self.ensure_one()
        self.sudo().write(
            {
                "state": "completed",
                "current_step": "completed",
                "completed_at": fields.Datetime.now(),
            }
        )

    def _fail(self, error, *, failure_code=None, outcome_uncertain=False):
        """
        Classify and record a failure.

        Sensitive data (tokens, headers, raw HTTP bodies) must NOT be
        stored in ``safe_failure_message`` or ``technical_failure_reference``.
        """
        self.ensure_one()

        # Classify
        error_text = str(error)
        is_access_error = "not allowed to access" in error_text or "AccessError" in type(error).__name__
        is_permanent = is_access_error or "contract_version" in error_text

        failure_state = (
            "reconciliation_required"
            if outcome_uncertain
            else ("permanent_failure" if is_permanent else "retryable_failure")
        )

        effective_failure_code = failure_code or (
            "document_access_contract_violation"
            if is_access_error
            else "integration_failure"
        )

        # Safe message: strip anything that looks like a token or URL
        safe_message = self._safe_error_text(error_text)

        self.sudo().write(
            {
                "state": failure_state,
                "failure_code": effective_failure_code,
                "safe_failure_message": safe_message[:500],
                "technical_failure_reference": self.correlation_id,
                "outcome_uncertain": outcome_uncertain,
                "requires_reconciliation": outcome_uncertain,
                "completed_at": fields.Datetime.now(),
            }
        )

    @staticmethod
    def _safe_error_text(error_text):
        """
        Return a safe summary of the error text.

        Removes tokens, SharePoint upload URLs, Graph auth headers, and
        provider credentials from the message before storage.
        """
        import re
        # Remove anything that looks like a bearer token or secret
        cleaned = re.sub(r"Bearer [A-Za-z0-9._\-+/=]{20,}", "[REDACTED_TOKEN]", error_text)
        # Remove upload session URLs
        cleaned = re.sub(
            r"https?://[^\s'\"]{40,}", "[REDACTED_URL]", cleaned
        )
        # Trim
        return cleaned[:500]

    # ------------------------------------------------------------------ #
    # Constraints                                                         #
    # ------------------------------------------------------------------ #

    _correlation_unique = models.Constraint(
        "unique(correlation_id)",
        "Integration operation correlation IDs must be unique.",
    )
