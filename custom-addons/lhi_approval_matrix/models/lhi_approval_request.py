# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class LhiApprovalRequest(models.Model):
    _name = "lhi.approval.request"
    _description = "LHI Active Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Request ID", required=True, copy=False, default=lambda self: _("New")
    )
    res_model = fields.Char(string="Resource Model", required=True, index=True)
    res_id = fields.Integer(string="Resource ID", required=True, index=True)

    matrix_id = fields.Many2one(
        "lhi.approval.matrix", string="Approval Matrix", readonly=True
    )
    document_type = fields.Selection(
        [
            ("purchase", "Purchase Request"),
            ("payment", "Payment Voucher"),
            ("travel", "Travel Request"),
            ("leave", "Leave Request"),
        ],
        string="Document Type",
        required=True,
    )

    amount = fields.Float(string="Amount", default=0.0)
    currency_id = fields.Many2one("res.currency", string="Currency")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned for Correction"),
            ("expired", "Expired"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    creator_id = fields.Many2one(
        "res.users",
        string="Creator/Initiator",
        required=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    line_ids = fields.One2many(
        "lhi.approval.request.line", "request_id", string="Approval Steps", copy=False
    )
    current_line_id = fields.Many2one(
        "lhi.approval.request.line",
        string="Current Step",
        compute="_compute_current_line",
        store=True,
    )

    # Criteria for matching (passed from source document)
    department_id = fields.Many2one("lhi.department", string="Department")
    office_id = fields.Many2one("lhi.office", string="Office/Location")
    donor_id = fields.Many2one("lhi.donor", string="Donor")
    award_id = fields.Many2one("lhi.award", string="Award/Grant")
    project_id = fields.Many2one("lhi.project", string="Project")
    funding_source_id = fields.Many2one("lhi.funding.source", string="Funding Source")
    procurement_method = fields.Selection(
        [
            ("direct", "Direct Sourcing"),
            ("rfq", "Request for Quotation"),
            ("tender", "Open Tender"),
        ],
        string="Procurement Method",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.approval.request"
                ) or _("New")
        return super(LhiApprovalRequest, self).create(vals_list)

    @api.depends("line_ids", "line_ids.state")
    def _compute_current_line(self):
        for record in self:
            current = record.line_ids.filtered(
                lambda request_line: request_line.state == "pending"
            )
            record.current_line_id = current[0] if current else False

    def action_submit(self):
        self.ensure_one()
        if self.state not in ["draft", "returned"]:
            raise UserError(_("Only draft or returned requests can be submitted."))

        self.action_prepare()
        return self.action_activate()

    def _lhi_resolve_matrix(self):
        """Resolve a matrix, allowing a source model to make a constrained choice.

        The source hook is useful for document categories (for example, a memo
        category) which select an existing matrix.  It deliberately receives the
        request record and must return an active matrix for the same company and
        document type.  Arbitrary client context cannot force a matrix.
        """
        self.ensure_one()
        source = self.env[self.res_model].browse(self.res_id).exists()
        matrix = self.env["lhi.approval.matrix"]
        if source and hasattr(source, "_lhi_approval_matrix_for_request"):
            matrix = source._lhi_approval_matrix_for_request(self)
        if not matrix:
            matrix = self.env["lhi.approval.matrix"].find_matching_matrix(
                document_type=self.document_type,
                amount=self.amount,
                currency_id=self.currency_id.id,
                department_id=self.department_id.id,
                office_id=self.office_id.id,
                donor_id=self.donor_id.id,
                award_id=self.award_id.id,
                project_id=self.project_id.id,
                funding_source_id=self.funding_source_id.id,
                procurement_method=self.procurement_method,
                company_id=self.company_id.id,
            )
        if matrix and (
            not matrix.active
            or matrix.company_id != self.company_id
            or matrix.document_type != self.document_type
        ):
            raise UserError(
                _("The selected approval matrix is not valid for this request.")
            )
        return matrix

    def action_prepare(self):
        """Snapshot the approval route without starting active approval.

        Signature-backed documents need to know the full recipient order while
        the provider draft is prepared, but the approval clock must only start
        after the requester's first signature is confirmed.
        """
        self.ensure_one()
        if self.state not in ["draft", "returned"]:
            raise UserError(_("Only draft or returned requests can be prepared."))

        matrix = self._lhi_resolve_matrix()

        if not matrix:
            raise UserError(
                _(
                    "No matching approval matrix found for the selected criteria and amount."
                )
            )

        # Remove old lines if resubmitting
        # Approval-step records are server-generated from the selected matrix.
        # Employees can submit requests but intentionally have no direct create/
        # unlink ACL on approval lines, so elevate only this deterministic operation.
        self.line_ids.sudo().unlink()

        # Instantiate lines
        line_vals = []
        for line in matrix.line_ids:
            # Resolve initial eligible approvers
            approver_users = line._lhi_resolve_approver_users(self)
            if not approver_users:
                raise UserError(
                    _("Approval stage '%s' has no eligible active approver.")
                    % line.name
                )

            line_vals.append(
                {
                    "request_id": self.id,
                    "matrix_line_id": line.id,
                    "name": line.name,
                    "sequence": line.sequence,
                    "approver_group_id": line.approver_group_id.id,
                    "approver_ids": [(6, 0, approver_users.ids)],
                    "approval_type": line.approval_type,
                    "timeout_days": line.timeout_days,
                    "escalation_user_id": line.escalation_user_id.id,
                    "state": "pending",
                }
            )

        self.env["lhi.approval.request.line"].sudo().create(line_vals)
        self.write({"matrix_id": matrix.id})
        self.message_post(
            body=_("Approval route prepared using matrix: %s") % matrix.name
        )
        return True

    def action_activate(self):
        """Start a previously snapshotted route."""
        self.ensure_one()
        if self.state not in ["draft", "returned"]:
            raise UserError(_("Only a draft or returned request can be activated."))
        if not self.matrix_id or not self.line_ids:
            raise UserError(_("Prepare the approval route before activating it."))
        self.write({"state": "under_review"})
        self._update_source_document("under_review")
        self.message_post(
            body=_("Approval Request submitted using matrix: %s") % self.matrix_id.name
        )

        # Log audit event
        self.env["lhi.audit.log"].create_event(
            event_type="approval_action",
            res_model=self._name,
            res_id=self.id,
            description=_("Approval Request submitted: %s") % self.name,
        )
        return True

    def _lhi_assert_current_approver(self):
        """Enforce the active-stage boundary for every approval decision."""
        self.ensure_one()
        if self.state != "under_review" or not self.current_line_id:
            raise UserError(_("This request is not currently under review."))

        current_line = self.current_line_id
        user = self.env.user
        if user == self.creator_id:
            raise UserError(
                _("Segregation of Duties: You cannot decide your own request.")
            )

        def is_eligible(candidate):
            if current_line.approver_group_id not in candidate.group_ids:
                return False
            # The request line is the immutable authorization snapshot.  Never
            # re-read the mutable matrix while deciding a submitted request.
            return candidate in current_line.approver_ids

        if is_eligible(user):
            return current_line

        delegations = self.env["lhi.approval.delegation"].search(
            [
                ("delegatee_id", "=", user.id),
                ("active", "=", True),
                ("start_date", "<=", fields.Datetime.now()),
                ("end_date", ">=", fields.Datetime.now()),
                ("document_type", "in", ["all", self.document_type]),
            ]
        )
        if any(is_eligible(delegation.delegator_id) for delegation in delegations):
            return current_line

        raise UserError(
            _("You are not authorized to decide this stage (%s).") % current_line.name
        )

    def action_approve(self, notes=None):
        current_line = self._lhi_assert_current_approver()
        user = self.env.user

        # Prevent duplicate approval in the same stage.
        if user in current_line.approved_user_ids:
            raise UserError(_("You have already approved this stage."))

        # Record approval
        current_line.write({"approved_user_ids": [(4, user.id)]})

        # History log
        self.env["lhi.approval.history"].create(
            {
                "request_line_id": current_line.id,
                "user_id": user.id,
                "action": "approve",
                "notes": notes or _("Approved"),
            }
        )

        # Check if stage is fully approved
        stage_complete = False
        if current_line.approval_type == "any":
            stage_complete = True
        elif current_line.approval_type == "all":
            # All eligible approvers must have approved
            if len(current_line.approved_user_ids) >= len(current_line.approver_ids):
                stage_complete = True

        if stage_complete:
            current_line.write({"state": "approved"})
            # Notify chatter
            self.message_post(
                body=_("Stage '%s' approved by %s.") % (current_line.name, user.name)
            )

            # Find next stage
            next_line = self.line_ids.filtered(
                lambda request_line: request_line.state == "pending"
            )
            if not next_line:
                self.write({"state": "approved"})
                self._update_source_document("approved")
                # Log audit event
                self.env["lhi.audit.log"].create_event(
                    event_type="approval_action",
                    res_model=self._name,
                    res_id=self.id,
                    description=_("Approval Request fully approved: %s") % self.name,
                )
        else:
            self.message_post(
                body=_(
                    "Stage '%s' approved by %s (Waiting for other parallel approvers)."
                )
                % (current_line.name, user.name)
            )

    def action_reject(self, notes=None):
        current_line = self._lhi_assert_current_approver()
        user = self.env.user
        if not (notes or "").strip():
            raise ValidationError(_("A rejection reason is required."))

        # History log
        self.env["lhi.approval.history"].create(
            {
                "request_line_id": current_line.id,
                "user_id": user.id,
                "action": "reject",
                "notes": notes,
            }
        )

        current_line.write({"state": "rejected"})
        self.write({"state": "rejected"})
        self._update_source_document("rejected")
        self.message_post(
            body=_("Request rejected at stage '%s' by %s. Notes: %s")
            % (current_line.name, user.name, notes or "")
        )

        # Log audit event
        self.env["lhi.audit.log"].create_event(
            event_type="approval_action",
            res_model=self._name,
            res_id=self.id,
            description=_("Approval Request rejected: %s") % self.name,
        )

    def action_return_for_correction(self, notes=None):
        current_line = self._lhi_assert_current_approver()
        user = self.env.user
        if not (notes or "").strip():
            raise ValidationError(_("A correction reason is required."))

        # History log
        self.env["lhi.approval.history"].create(
            {
                "request_line_id": current_line.id,
                "user_id": user.id,
                "action": "return",
                "notes": notes,
            }
        )

        # Reset all steps and mark request as returned
        self.line_ids.write({"state": "pending", "approved_user_ids": [(6, 0, [])]})
        self.write({"state": "returned"})
        self._update_source_document("returned")
        self.message_post(
            body=_("Request returned for correction by %s. Notes: %s")
            % (user.name, notes or "")
        )

    def check_and_escalate_timeouts(self):
        """Scheduled action runner to handle stage timeouts and escalations."""
        now = fields.Datetime.now()
        under_review_reqs = self.search([("state", "=", "under_review")])
        for req in under_review_reqs:
            line = req.current_line_id
            if line and line.timeout_days > 0:
                # Find start date of current stage (last action date of previous stage or request creation/submission date)
                start_date = req.write_date
                # Find history logs for this stage
                histories = line.history_ids.sorted(
                    key=lambda h: h.action_date, reverse=True
                )
                if histories:
                    start_date = histories[0].action_date

                limit_date = start_date + timedelta(days=line.timeout_days)
                if now > limit_date:
                    if line.escalation_user_id:
                        # Perform escalation: add escalation user to specific approvers and post notice
                        line.write({"approver_ids": [(4, line.escalation_user_id.id)]})
                        req.message_post(
                            body=_("Approval step '%s' timed out. Escalated to %s.")
                            % (line.name, line.escalation_user_id.name)
                        )
                        # Log history
                        self.env["lhi.approval.history"].create(
                            {
                                "request_line_id": line.id,
                                "user_id": self.env.ref("base.user_root").id,
                                "action": "escalate",
                                "notes": _("System Escalation due to timeout."),
                            }
                        )
                    else:
                        # No escalation user, expire request
                        req.write({"state": "expired"})
                        req._update_source_document("expired")
                        line.write({"state": "rejected"})
                        req.message_post(
                            body=_("Approval step '%s' timed out. Request expired.")
                            % line.name
                        )

    def _update_source_document(self, target_state):
        """Helper to write status/chatter back to the source record."""
        self.ensure_one()
        try:
            source_rec = self.env[self.res_model].browse(self.res_id)
            if source_rec.exists():
                message = _("Approval Request %s state changed to %s.") % (
                    self.name,
                    target_state,
                )
                source_rec.message_post(body=message)
                if hasattr(source_rec, "write"):
                    # Update fields if source model contains standard workflow state fields
                    vals = {}
                    if "lhi_approval_state" in source_rec._fields:
                        vals["lhi_approval_state"] = target_state
                    if vals:
                        source_rec.write(vals)
        except Exception:
            pass


class LhiApprovalRequestLine(models.Model):
    _name = "lhi.approval.request.line"
    _description = "LHI Active Approval Step"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "lhi.approval.request",
        string="Approval Request",
        ondelete="cascade",
        required=True,
    )
    matrix_line_id = fields.Many2one(
        "lhi.approval.matrix.line", string="Configured Line", ondelete="set null"
    )
    name = fields.Char(string="Step Name", required=True)
    sequence = fields.Integer(string="Sequence/Step", default=10)

    approver_group_id = fields.Many2one(
        "res.groups", string="Approver Group", required=True
    )
    approver_ids = fields.Many2many(
        "res.users",
        "lhi_approval_req_line_approvers_rel",
        "line_id",
        "user_id",
        string="Eligible Approvers",
    )
    approved_user_ids = fields.Many2many(
        "res.users",
        "lhi_approval_req_line_approved_rel",
        "line_id",
        "user_id",
        string="Approved By",
    )

    approval_type = fields.Selection(
        [
            ("any", "Any Approver"),
            ("all", "All Approvers"),
        ],
        string="Approval Type",
        required=True,
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="pending",
        required=True,
    )

    timeout_days = fields.Integer(string="Timeout (Days)", default=3)
    escalation_user_id = fields.Many2one("res.users", string="Escalation Approver")

    history_ids = fields.One2many(
        "lhi.approval.history", "request_line_id", string="History"
    )


class LhiApprovalHistory(models.Model):
    _name = "lhi.approval.history"
    _description = "LHI Approval History Log"
    _order = "action_date desc"

    request_line_id = fields.Many2one(
        "lhi.approval.request.line",
        string="Approval Step",
        ondelete="cascade",
        required=True,
    )
    user_id = fields.Many2one("res.users", string="Done By", required=True)
    action = fields.Selection(
        [
            ("approve", "Approve"),
            ("reject", "Reject"),
            ("return", "Return for Correction"),
            ("escalate", "Escalate"),
        ],
        string="Action",
        required=True,
    )
    notes = fields.Text(string="Notes")
    action_date = fields.Datetime(
        string="Date/Time", default=fields.Datetime.now, required=True
    )
