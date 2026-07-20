from odoo import models, fields, _
from odoo.exceptions import ValidationError

class LhiMediaRequest(models.Model):
    _name = "lhi.media.request"
    _inherit = ["lhi.media.request", "lhi.project.funded.gate.mixin"]

    def action_submit(self):
        for record in self:
            record._check_project_funded_memo(record.project_id, record.workplan_activity_id)
            if record.state not in ("draft", "revision"):
                raise ValidationError(_("Only draft or returned Media requests can be submitted."))
        self.write({"state": "submitted"})

class LhiProject(models.Model):
    _inherit = "lhi.project"

    media_request_ids = fields.One2many("lhi.media.request", "project_id")

class LhiWorkplanActivity(models.Model):
    _inherit = "lhi.workplan.activity"

    programme_media_request_ids = fields.One2many("lhi.media.request", "workplan_activity_id")
