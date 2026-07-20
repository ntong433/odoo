from odoo import models, fields

class LhiMealData(models.Model):
    _name = "lhi.meal.data"
    _inherit = ["lhi.meal.data", "lhi.project.funded.gate.mixin"]

    grant_id = fields.Many2one("lhi.award", tracking=True)

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.activity_id)
        return super().action_submit()


class LhiMealInitiative(models.Model):
    _name = "lhi.meal.initiative"
    _inherit = ["lhi.meal.initiative", "lhi.project.funded.gate.mixin"]

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.activity_id)
        return super().action_submit()


class LhiProject(models.Model):
    _inherit = "lhi.project"

    programme_meal_initiative_ids = fields.One2many("lhi.meal.initiative", "project_id")


class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_meal_data_ids = fields.One2many("lhi.meal.data", "activity_id")
    programme_meal_initiative_ids = fields.One2many("lhi.meal.initiative", "activity_id")
