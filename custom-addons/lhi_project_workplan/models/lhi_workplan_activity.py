# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiWorkplanActivity(models.Model):
    _name = 'lhi.workplan.activity'
    _description = 'Workplan Hierarchy Element'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title/Description', required=True, tracking=True)
    code = fields.Char(string='Activity Code', tracking=True)
    workplan_id = fields.Many2one('lhi.workplan', string='Workplan', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='workplan_id.company_id', store=True)
    project_id = fields.Many2one(related='workplan_id.project_id', store=True)
    
    element_type = fields.Selection([
        ('outcome', 'Outcome'),
        ('output', 'Output'),
        ('activity', 'Activity'),
        ('subactivity', 'Sub-Activity')
    ], string='Hierarchy Level', required=True, tracking=True)
    
    parent_id = fields.Many2one('lhi.workplan.activity', string='Parent Element', index=True, ondelete='cascade')
    child_ids = fields.One2many('lhi.workplan.activity', 'parent_id', string='Child Elements')
    
    responsible_id = fields.Many2one('res.users', string='Responsible Officer', tracking=True)
    location_id = fields.Many2one('lhi.office', string='Location')
    
    planned_start = fields.Date(string='Planned Start', tracking=True)
    planned_end = fields.Date(string='Planned End', tracking=True)
    actual_start = fields.Date(string='Actual Start', tracking=True)
    actual_end = fields.Date(string='Actual End', tracking=True)
    
    target_value = fields.Float(string='Target Quantity')
    achieved_value = fields.Float(string='Achieved Quantity', tracking=True)
    unit = fields.Char(string='Unit of Measure (e.g. Beneficiaries, Trainings)')
    
    budget_line = fields.Char(string='Budget Line Reference')
    procurement_required = fields.Boolean(string='Procurement Required')
    fleet_required = fields.Boolean(string='Fleet Required')
    is_milestone = fields.Boolean(string='Is Milestone')
    evidence_requirements = fields.Text(string='Evidence Requirements')
    
    dependency_ids = fields.Many2many('lhi.workplan.activity', 'lhi_activity_dependency_rel', 'activity_id', 'depends_on_id', string='Dependencies')
    
    odoo_task_id = fields.Many2one('project.task', string='Linked Execution Task', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, required=True)

    @api.constrains('planned_start', 'planned_end')
    def _check_dates(self):
        for record in self:
            if record.planned_start and record.planned_end and record.planned_start > record.planned_end:
                raise ValidationError(_("The planned start date cannot be later than the planned end date."))
                
    def action_generate_task(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_("You can only generate execution tasks for approved activities."))
        if self.element_type not in ['activity', 'subactivity']:
            raise ValidationError(_("Only Activities and Sub-Activities can generate execution tasks."))
        if self.odoo_task_id:
            raise ValidationError(_("An execution task already exists for this activity."))
            
        # Get the execution project
        odoo_project = self.project_id.odoo_project_id
        if not odoo_project:
            raise ValidationError(_("The LHI Project is not linked to an Odoo Execution Project. Please activate the project or link it manually."))
            
        task_vals = {
            'name': f"[{self.code or 'N/A'}] {self.name}",
            'project_id': odoo_project.id,
            'user_ids': [(4, self.responsible_id.id)] if self.responsible_id else False,
            'date_deadline': self.planned_end,
            'company_id': self.company_id.id,
        }
        
        # If it's a subactivity, try to find parent task
        if self.element_type == 'subactivity' and self.parent_id and self.parent_id.odoo_task_id:
            task_vals['parent_id'] = self.parent_id.odoo_task_id.id
            
        task = self.env['project.task'].create(task_vals)
        self.odoo_task_id = task.id
        self.state = 'in_progress'

    @api.model
    def _cron_check_delayed_activities(self):
        today = fields.Date.context_today(self)
        delayed_activities = self.search([
            ('state', 'in', ['approved', 'in_progress']),
            ('planned_end', '<', today)
        ])
        for act in delayed_activities:
            act.state = 'delayed'
            if act.responsible_id:
                act.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=act.responsible_id.id,
                    summary=_('Activity Delayed: %s') % act.name
                )
