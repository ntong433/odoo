import hashlib
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LhiMemoIntegration(models.Model):
    """
    Extends lhi.memo with saga operation tracking and preflight orchestration.

    ``action_prepare_and_sign`` is intentionally NOT overridden here.  The
    gateway-safe implementation in ``lhi_memo_management.models.memo`` is the
    single authoritative implementation.  This extension only adds the saga
    operation linkage fields and the preflight validation helper that is called
    by that implementation.

    All ``lhi.document.item`` access in this module uses ``sudo()`` guards or
    ``MemoDocumentGateway`` as mandated by the Memo document contract.
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
        """
        Preflight stage: validates all prerequisites before making external
        writes or API calls.

        Called by ``lhi_memo_management``'s gateway-safe
        ``action_prepare_and_sign``.  Uses ``sudo()`` for the document
        availability check because normal Memo employees have no ACL on
        ``lhi.document.item``.
        """
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

        # 6. Template & SharePoint DOCX item check.
        # NOTE: Normal Memo employees have no ACL on lhi.document.item.
        # This service-boundary check uses sudo() before the gateway is
        # available (gateway requires a memo record; preflight runs first).
        sudo_self = self.sudo()
        if not sudo_self.source_docx_item_id:
            raise UserError(
                _("The Word document template is missing or not confirmed in SharePoint.")
            )
        if sudo_self.source_docx_item_id.storage_state != "available":
            raise UserError(
                _("The Word document template is missing or not confirmed in SharePoint.")
            )

        # 7. SharePoint storage policy (sudo needed for company-scoped resolver)
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
