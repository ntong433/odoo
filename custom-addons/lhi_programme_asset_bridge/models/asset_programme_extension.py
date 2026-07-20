from odoo import models, fields

class LhiAsset(models.Model):
    _name = "lhi.asset"
    _inherit = ["lhi.asset"]

    work_context = fields.Selection(
        [("project_linked", "Project-linked"), ("standalone_departmental", "Standalone departmental")], 
        default="standalone_departmental", required=True, tracking=True
    )
    award_id = fields.Many2one("lhi.award", string="Grant/Award", tracking=True)
    workplan_activity_id = fields.Many2one("lhi.workplan.activity", tracking=True)
    memo_id = fields.Many2one("lhi.activity.memo", tracking=True)
    project_budget_line_id = fields.Many2one("lhi.project.budget.line", tracking=True)

class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_asset_ids = fields.One2many("lhi.asset", "project_id")

class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_asset_ids = fields.One2many("lhi.asset", "workplan_activity_id")
