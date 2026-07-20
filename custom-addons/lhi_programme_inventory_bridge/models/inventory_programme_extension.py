from odoo import models, fields, api

WORK_CONTEXT = [("project_linked", "Project-linked"), ("standalone_departmental", "Standalone departmental")]

class StockMove(models.Model):
    _inherit = ["stock.move", "lhi.project.funded.gate.mixin"]

    lhi_grant_id = fields.Many2one("lhi.award", string="Grant/Award")
    
    # Redefine mixin fields to disable tracking, since stock.move doesn't support it natively
    work_context = fields.Selection(WORK_CONTEXT, default="standalone_departmental", required=True, tracking=False)
    memo_id = fields.Many2one("lhi.activity.memo", string="Approved Activity Memo", tracking=False)
    project_budget_line_id = fields.Many2one("lhi.project.budget.line", string="Project Budget Line", tracking=False)

    @api.constrains("work_context", "lhi_project_id", "lhi_activity_id", "memo_id", "project_budget_line_id")
    def _check_lhi_project_scope(self):
        for record in self:
            record._check_project_funded_memo(record.lhi_project_id, record.lhi_activity_id)

class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_stock_move_ids = fields.One2many("stock.move", "lhi_project_id")

class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_stock_move_ids = fields.One2many("stock.move", "lhi_activity_id")
