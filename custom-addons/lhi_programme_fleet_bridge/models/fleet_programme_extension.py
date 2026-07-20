from odoo import models, fields

class LhiFleetTrip(models.Model):
    _name = "lhi.fleet.trip"
    _inherit = ["lhi.fleet.trip", "lhi.project.funded.gate.mixin"]

    grant_id = fields.Many2one("lhi.award", tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.lhi_project_id, record.lhi_activity_id)
        return super().action_submit()

class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_fleet_trip_ids = fields.One2many("lhi.fleet.trip", "lhi_project_id")

class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_fleet_trip_ids = fields.One2many("lhi.fleet.trip", "lhi_activity_id")
