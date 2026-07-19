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


class LhiPurchaseRequest(models.Model):
    _inherit = ["lhi.purchase.request", "lhi.project.funded.gate.mixin"]

    workplan_activity_id = fields.Many2one("lhi.workplan.activity", string="Workplan Activity", tracking=True)
    enterprise_payment_reference = fields.Char(tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.workplan_activity_id)
        return super().action_submit()


class LhiFleetTrip(models.Model):
    _inherit = ["lhi.fleet.trip", "lhi.project.funded.gate.mixin"]

    grant_id = fields.Many2one("lhi.award", tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.lhi_project_id, record.lhi_activity_id)
        return super().action_submit()


class LhiMediaRequest(models.Model):
    _inherit = ["lhi.media.request", "lhi.project.funded.gate.mixin"]

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.workplan_activity_id)
            if record.state not in ("draft", "revision"):
                raise ValidationError(_("Only draft or returned Media requests can be submitted."))
        self.write({"state": "submitted"})


class LhiMealData(models.Model):
    _inherit = ["lhi.meal.data", "lhi.project.funded.gate.mixin"]

    grant_id = fields.Many2one("lhi.award", tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.activity_id)
        return super().action_submit()


class LhiMealInitiative(models.Model):
    _inherit = ["lhi.meal.initiative", "lhi.project.funded.gate.mixin"]

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.activity_id)
        return super().action_submit()


class StockMove(models.Model):
    _inherit = ["stock.move", "lhi.project.funded.gate.mixin"]

    lhi_grant_id = fields.Many2one("lhi.award", string="Grant/Award")

    @api.constrains("work_context", "lhi_project_id", "lhi_activity_id", "memo_id", "project_budget_line_id")
    def _check_lhi_project_scope(self):
        for record in self:
            record._check_project_funded_memo(record.lhi_project_id, record.lhi_activity_id)


class LhiAsset(models.Model):
    _inherit = "lhi.asset"

    work_context = fields.Selection(WORK_CONTEXT, default="standalone_departmental", required=True, tracking=True)
    award_id = fields.Many2one("lhi.award", string="Grant/Award", tracking=True)
    workplan_activity_id = fields.Many2one("lhi.workplan.activity", tracking=True)
    memo_id = fields.Many2one("lhi.activity.memo", tracking=True)
    project_budget_line_id = fields.Many2one("lhi.project.budget.line", tracking=True)


class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_budget_ids = fields.One2many("lhi.project.budget", "project_id")
    activity_memo_ids = fields.One2many("lhi.activity.memo", "project_id")
    execution_request_ids = fields.One2many("lhi.execution.request", "project_id")
    payment_retirement_ids = fields.One2many("lhi.payment.retirement", "project_id")
    programme_meal_initiative_ids = fields.One2many("lhi.meal.initiative", "project_id")
    programme_purchase_request_ids = fields.One2many("lhi.purchase.request", "project_id")
    programme_fleet_trip_ids = fields.One2many("lhi.fleet.trip", "lhi_project_id")
    programme_asset_ids = fields.One2many("lhi.asset", "project_id")
    programme_stock_move_ids = fields.One2many("stock.move", "lhi_project_id")


class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_allocation_ids = fields.One2many("lhi.activity.budget.allocation", "activity_id")
    activity_memo_ids = fields.One2many("lhi.activity.memo", "activity_id")
    execution_request_ids = fields.One2many("lhi.execution.request", "activity_id")
    payment_retirement_ids = fields.One2many("lhi.payment.retirement", "activity_id")
    programme_meal_data_ids = fields.One2many("lhi.meal.data", "activity_id")
    programme_meal_initiative_ids = fields.One2many("lhi.meal.initiative", "activity_id")
    programme_media_request_ids = fields.One2many("lhi.media.request", "workplan_activity_id")
    programme_purchase_request_ids = fields.One2many("lhi.purchase.request", "workplan_activity_id")
    programme_fleet_trip_ids = fields.One2many("lhi.fleet.trip", "lhi_activity_id")
    programme_asset_ids = fields.One2many("lhi.asset", "workplan_activity_id")
    programme_stock_move_ids = fields.One2many("stock.move", "lhi_activity_id")
