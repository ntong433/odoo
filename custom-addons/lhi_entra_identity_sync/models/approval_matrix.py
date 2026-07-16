from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class LhiApprovalMatrixLine(models.Model):
    _inherit = "lhi.approval.matrix.line"

    approver_source = fields.Selection(
        [
            ("group", "Existing Odoo Group"),
            ("requester_manager", "Requester's Synchronized Manager"),
        ],
        default="group",
        required=True,
        help=(
            "Manager resolution uses the request creator's synchronized HR reporting "
            "line when a new approval request is submitted. Existing requests retain "
            "their snapshotted approvers."
        ),
    )

    def _lhi_resolve_approver_users(self, request):
        self.ensure_one()
        if self.approver_source != "requester_manager":
            return super()._lhi_resolve_approver_users(request)
        employee = request.creator_id.sudo().employee_id
        manager = employee.parent_id.user_id if employee and employee.parent_id else False
        if not manager or not manager.active:
            raise UserError(
                _(
                    "The request creator has no active synchronized Odoo manager. "
                    "Submit after the manager mapping is corrected."
                )
            )
        if self.approver_group_id not in manager.group_ids:
            raise UserError(
                _(
                    "The synchronized manager does not hold the configured existing "
                    "Odoo approver group."
                )
            )
        if self.approver_ids and manager not in self.approver_ids:
            raise UserError(
                _("The synchronized manager is not in this stage's allowed approver list.")
            )
        return manager


class LhiApprovalRequest(models.Model):
    _inherit = "lhi.approval.request"

    manager_reassignment_count = fields.Integer(readonly=True, copy=False)

    def action_reassign_synchronized_manager(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_manager"):
            raise AccessError(_("Only an LHI manager may reassign an approval manager."))
        if self.state != "under_review" or not self.current_line_id:
            raise UserError(_("Only the current step of an active request can be reassigned."))
        matrix_line = self.current_line_id.matrix_line_id
        if not matrix_line or matrix_line.approver_source != "requester_manager":
            raise UserError(_("The current approval step is not manager-resolved."))
        new_manager = matrix_line._lhi_resolve_approver_users(self)
        old_approvers = self.current_line_id.approver_ids
        if old_approvers == new_manager:
            raise UserError(_("The snapshotted approver is already the current manager."))
        self.current_line_id.write({"approver_ids": [(6, 0, new_manager.ids)]})
        self.write(
            {"manager_reassignment_count": self.manager_reassignment_count + 1}
        )
        self.env["lhi.approval.history"].create(
            {
                "request_line_id": self.current_line_id.id,
                "user_id": self.env.user.id,
                "action": "reassign",
                "notes": _(
                    "Explicit manager reassignment from %s to %s after Entra manager change."
                )
                % (
                    ", ".join(old_approvers.mapped("name")) or _("No approver"),
                    new_manager.name,
                ),
            }
        )
        self.message_post(
            body=_(
                "Manager approver explicitly reassigned to %s by %s. "
                "No submitted approval is changed automatically."
            )
            % (new_manager.name, self.env.user.name)
        )
        self.env["lhi.audit.log"].create_event(
            event_type="approval_action",
            res_model=self._name,
            res_id=self.id,
            description=_("Synchronized manager approver explicitly reassigned."),
            old_value=old_approvers.ids,
            new_value=new_manager.ids,
        )
        return True


class LhiApprovalHistory(models.Model):
    _inherit = "lhi.approval.history"

    action = fields.Selection(
        selection_add=[("reassign", "Explicit Manager Reassignment")],
        ondelete={"reassign": "cascade"},
    )
