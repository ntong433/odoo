# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProjectActivation(models.Model):
    _inherit = 'lhi.project'

    state = fields.Selection([
        ('setup', 'Setup & Activation'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string='Status', default='setup', required=True, tracking=True)

    # Project Activation Checklist
    chk_signed_agreement = fields.Boolean(string='Signed Agreement Received', tracking=True)
    chk_approved_budget = fields.Boolean(string='Approved Budget Uploaded', tracking=True)
    chk_workplan = fields.Boolean(string='Workplan Approved', tracking=True)
    chk_project_team = fields.Boolean(string='Project Team Configured', tracking=True)
    chk_project_code = fields.Boolean(string='Project Code Active', tracking=True)
    chk_procurement_plan = fields.Boolean(string='Procurement Plan Uploaded', tracking=True)
    chk_meal_setup = fields.Boolean(string='MEAL Framework Setup', tracking=True)
    chk_risk_register = fields.Boolean(string='Risk Register Active', tracking=True)
    chk_reporting_calendar = fields.Boolean(string='Reporting Calendar Setup', tracking=True)
    chk_focal_persons = fields.Boolean(string='Focal Persons Assigned', tracking=True)
    
    # Focal Persons
    focal_pm_id = fields.Many2one('res.users', string='Project Manager')
    focal_finance_id = fields.Many2one('res.users', string='Finance Focal Point')
    focal_meal_id = fields.Many2one('res.users', string='MEAL Focal Point')

    @api.onchange('focal_pm_id', 'focal_finance_id', 'focal_meal_id')
    def _onchange_focal_persons(self):
        if self.focal_pm_id and self.focal_finance_id and self.focal_meal_id:
            self.chk_focal_persons = True

    def action_activate_project(self):
        self.ensure_one()
        # Verify Checklist
        checklist = [
            (self.chk_signed_agreement, 'Signed Agreement Received'),
            (self.chk_approved_budget, 'Approved Budget Uploaded'),
            (self.chk_workplan, 'Workplan Approved'),
            (self.chk_project_team, 'Project Team Configured'),
            (self.chk_project_code, 'Project Code Active'),
            (self.chk_procurement_plan, 'Procurement Plan Uploaded'),
            (self.chk_meal_setup, 'MEAL Framework Setup'),
            (self.chk_risk_register, 'Risk Register Active'),
            (self.chk_reporting_calendar, 'Reporting Calendar Setup'),
            (self.chk_focal_persons, 'Focal Persons Assigned')
        ]
        
        missing = [item[1] for item in checklist if not item[0]]
        
        if missing:
            raise ValidationError(_("Cannot activate the project. The following mandatory setup requirements are not approved:\n%s") % '\n'.join(missing))
            
        self.state = 'active'
        self.active = True
        
    def action_close_project(self):
        self.ensure_one()
        self.state = 'closed'
        self.active = False
