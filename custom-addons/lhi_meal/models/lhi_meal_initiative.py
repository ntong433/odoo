from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiMealInitiative(models.Model):
    _name = "lhi.meal.initiative"
    _description = "MEAL Initiative"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    work_context = fields.Selection([("project_linked", "Project-linked"), ("standalone_departmental", "Standalone departmental")], default="standalone_departmental", required=True, tracking=True)
    initiative_type = fields.Selection([("baseline", "Baseline Survey"), ("assessment", "Assessment"), ("dqa", "Data Quality Assessment"), ("evaluation", "Evaluation"), ("monitoring", "Field Monitoring"), ("learning", "Learning Review")], required=True, tracking=True)
    project_id = fields.Many2one("lhi.project", tracking=True)
    grant_id = fields.Many2one("lhi.award", tracking=True)
    activity_id = fields.Many2one("lhi.workplan.activity", tracking=True)
    manager_id = fields.Many2one("res.users", default=lambda self: self.env.user, tracking=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    purpose = fields.Text(required=True)
    findings = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("in_progress", "In Progress"), ("completed", "Completed"), ("closed", "Closed"), ("cancelled", "Cancelled")], default="draft", required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    @api.constrains("date_start", "date_end", "project_id", "activity_id")
    def _check_scope(self):
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError(_("The initiative end date cannot precede its start date."))
            if record.activity_id and record.activity_id.project_id != record.project_id:
                raise ValidationError(_("The selected activity must belong to the initiative project."))

    def action_submit(self):
        for record in self:
            if record.work_context == "project_linked" and not record.project_id:
                raise ValidationError(_("A project-linked MEAL initiative requires a project."))
            record.state = "submitted"
