from odoo import models, fields

class LhiPurchaseRequest(models.Model):
    _name = "lhi.purchase.request"
    _inherit = ["lhi.purchase.request", "lhi.project.funded.gate.mixin"]

    workplan_activity_id = fields.Many2one("lhi.workplan.activity", string="Workplan Activity", tracking=True)
    enterprise_payment_reference = fields.Char(tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.workplan_activity_id)
        return super().action_submit()

class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_purchase_request_ids = fields.One2many("lhi.purchase.request", "project_id")

class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_purchase_request_ids = fields.One2many("lhi.purchase.request", "workplan_activity_id")
