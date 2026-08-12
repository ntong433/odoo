from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


WORK_CONTEXT = [
    ("project_linked", "Project-linked"),
    ("standalone_departmental", "Standalone departmental"),
]


class ProjectFundedGateMixin(models.AbstractModel):
    _name = "lhi.project.funded.gate.mixin"
    _description = "Project-funded Memo Gate"

    work_context = fields.Selection(
        WORK_CONTEXT,
        default="standalone_departmental",
        required=True,
        tracking=True,
    )

    memo_id = fields.Many2one(
        "lhi.memo",
        string="Approved Project Memo",
        tracking=True,
    )

    project_budget_line_id = fields.Many2one(
        "lhi.project.budget.line",
        string="Project Budget Line",
        tracking=True,
    )

    def _check_project_funded_memo(self, project, activity):
        self.ensure_one()

        if self.work_context != "project_linked":
            return

        if (
            not project
            or not activity
            or not self.memo_id
            or not self.project_budget_line_id
        ):
            raise ValidationError(
                _(
                    "Project-linked work requires a project, "
                    "workplan activity, signed memo, and project "
                    "budget line."
                )
            )

        memo = self.memo_id

        if memo.state != "completed":
            raise ValidationError(
                _(
                    "Project-funded execution requires a signed "
                    "and completed LHI Memo."
                )
            )

        if memo.work_context != "project_linked":
            raise ValidationError(
                _("The selected memo is not a project-linked memo.")
            )

        if memo.project_id != project:
            raise ValidationError(
                _("The selected memo does not belong to this project.")
            )

        if memo.workplan_activity_id != activity:
            raise ValidationError(
                _(
                    "The selected memo does not belong to this "
                    "workplan activity."
                )
            )

        if (
            memo.project_budget_line_id
            != self.project_budget_line_id
        ):
            raise ValidationError(
                _(
                    "The memo budget line does not match the "
                    "operational request budget line."
                )
            )


class LhiMemoProgrammeContext(models.Model):
    _inherit = "lhi.memo"

    workplan_activity_id = fields.Many2one(
        "lhi.workplan.activity",
        string="Workplan Activity",
        tracking=True,
        index=True,
    )

    project_budget_line_id = fields.Many2one(
        "lhi.project.budget.line",
        string="Project Budget Line",
        tracking=True,
        index=True,
    )

    @api.constrains(
        "work_context",
        "project_id",
        "workplan_activity_id",
        "project_budget_line_id",
    )
    def _check_programme_context(self):
        for memo in self:
            if memo.work_context != "project_linked":
                continue

            if (
                memo.workplan_activity_id
                and memo.project_id
                and memo.workplan_activity_id.project_id
                != memo.project_id
            ):
                raise ValidationError(
                    _(
                        "The selected workplan activity does not "
                        "belong to the memo project."
                    )
                )

            if (
                memo.project_budget_line_id
                and memo.project_id
                and memo.project_budget_line_id.budget_id.project_id
                != memo.project_id
            ):
                raise ValidationError(
                    _(
                        "The selected project budget line does not "
                        "belong to the memo project."
                    )
                )


class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_budget_ids = fields.One2many(
        "lhi.project.budget",
        "project_id",
    )

    # Temporary legacy compatibility only.
    # lhi.activity.memo is no longer exposed to users.
    activity_memo_ids = fields.One2many(
        "lhi.activity.memo",
        "project_id",
    )

    execution_request_ids = fields.One2many(
        "lhi.execution.request",
        "project_id",
    )

    payment_retirement_ids = fields.One2many(
        "lhi.payment.retirement",
        "project_id",
    )


class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_allocation_ids = fields.One2many(
        "lhi.activity.budget.allocation",
        "activity_id",
    )

    # Temporary legacy compatibility only.
    # lhi.activity.memo is no longer exposed to users.
    activity_memo_ids = fields.One2many(
        "lhi.activity.memo",
        "activity_id",
    )

    execution_request_ids = fields.One2many(
        "lhi.execution.request",
        "activity_id",
    )

    payment_retirement_ids = fields.One2many(
        "lhi.payment.retirement",
        "activity_id",
    )
