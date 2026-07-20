from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

WORK_CONTEXT = [("project_linked", "Project-linked"), ("standalone_departmental", "Standalone departmental")]


class ProjectFundedGateMixin(models.AbstractModel):
    _name = "lhi.project.funded.gate.mixin"
    _description = "Project-funded Memo Gate"

    work_context = fields.Selection(WORK_CONTEXT, default="standalone_departmental", required=True, tracking=True)
    memo_id = fields.Many2one("lhi.activity.memo", string="Approved Activity Memo", tracking=True)
    project_budget_line_id = fields.Many2one("lhi.project.budget.line", string="Project Budget Line", tracking=True)

    def _check_project_funded_memo(self, project, activity):
        self.ensure_one()
        if self.work_context != "project_linked":
            return
        if not project or not activity or not self.memo_id or not self.project_budget_line_id:
            raise ValidationError(_("Project-linked work requires project, activity, approved memo, and project budget line."))
        if self.memo_id.state != "approved":
            raise ValidationError(_("No approved activity memo, no project-funded execution request."))
        if self.memo_id.project_id != project or self.memo_id.activity_id != activity or self.memo_id.budget_line_id != self.project_budget_line_id:
            raise ValidationError(_("The memo, activity, budget line, and project must match."))


class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_budget_ids = fields.One2many("lhi.project.budget", "project_id")
    activity_memo_ids = fields.One2many("lhi.activity.memo", "project_id")
    execution_request_ids = fields.One2many("lhi.execution.request", "project_id")
    payment_retirement_ids = fields.One2many("lhi.payment.retirement", "project_id")


class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_allocation_ids = fields.One2many("lhi.activity.budget.allocation", "activity_id")
    activity_memo_ids = fields.One2many("lhi.activity.memo", "activity_id")
    execution_request_ids = fields.One2many("lhi.execution.request", "activity_id")
    payment_retirement_ids = fields.One2many("lhi.payment.retirement", "activity_id")
