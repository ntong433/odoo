# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiWorkplan(models.Model):
    _name = 'lhi.workplan'
    _description = 'Project Workplan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True, tracking=True)
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    plan_type = fields.Selection([
        ('annual', 'Annual Workplan'),
        ('quarterly', 'Quarterly Workplan'),
        ('monthly', 'Monthly Workplan')
    ], string='Workplan Type', required=True, tracking=True)
    
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('revised', 'Revised/Archived')
    ], string='Status', default='draft', tracking=True, required=True)
    
    version = fields.Integer(string='Version', default=1, copy=False)
    parent_id = fields.Many2one('lhi.workplan', string='Previous Version', copy=False)
    
    # Keep mail.activity.mixin's ``activity_ids`` field intact for the chatter.
    # Reusing that reserved field name changes its comodel and breaks inherited
    # related fields such as activity_type_icon during registry setup.
    workplan_activity_ids = fields.One2many(
        'lhi.workplan.activity',
        'workplan_id',
        string='Workplan Activities',
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def action_submit(self):
        self.state = 'submitted'

    def action_approve(self):
        self.state = 'approved'
        # Approve all associated activities automatically
        self.workplan_activity_ids.write({'state': 'approved'})

    def action_create_revision(self):
        self.ensure_one()
        # Create a copy and increment version
        new_plan = self.copy({
            'state': 'draft',
            'version': self.version + 1,
            'parent_id': self.id,
            'name': f"{self.name} (v{self.version + 1})"
        })
        self.state = 'revised'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.workplan',
            'res_id': new_plan.id,
            'view_mode': 'form',
            'target': 'current'
        }
