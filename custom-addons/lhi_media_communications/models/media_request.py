# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MediaRequest(models.Model):
    _name = 'lhi.media.request'
    _description = 'Media Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: 'New')
    title = fields.Char(string='Title', required=True, tracking=True)
    requesting_unit_id = fields.Many2one('hr.department', string='Requesting Unit', tracking=True)
    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, tracking=True)
    
    work_context = fields.Selection(
        [
            ("standalone_departmental", "Standalone Departmental"),
            ("project_linked", "Project-linked")
        ],
        string="Work Context",
        default="standalone_departmental",
        required=True,
        tracking=True
    )
    
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    task_id = fields.Many2one('project.task', string='Project Task')
    workplan_activity_id = fields.Many2one('lhi.workplan.activity', string='Workplan Activity')
    grant_id = fields.Many2one('lhi.award', string='Grant/Award')
    
    activity_type = fields.Selection([
        ('outreach', 'Outreach Coverage'),
        ('radio', 'Radio Programme'),
        ('interview', 'Media Interview'),
        ('photo_video', 'Photography & Video'),
        ('press_release', 'Press Release'),
        ('newsletter', 'Newsletter'),
        ('social_media', 'Social Media Content'),
        ('campaign', 'Campaign'),
        ('event', 'Event Coverage'),
        ('iec', 'IEC & Visibility Material'),
        ('donor_visibility', 'Donor Visibility Activity'),
        ('other', 'Other')
    ], string='Activity Type', required=True, tracking=True)
    
    purpose = fields.Text(string='Purpose', required=True)
    target_audience = fields.Char(string='Target Audience')
    location = fields.Char(string='Location')
    
    requested_date = fields.Date(string='Requested Date', default=fields.Date.context_today)
    required_completion_date = fields.Date(string='Required Completion Date', required=True, tracking=True)
    
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'High'),
        ('2', 'Urgent')
    ], string='Priority', default='0', tracking=True)
    
    key_message = fields.Text(string='Key Message')
    donor_branding_requirements = fields.Text(string='Donor Branding Requirements')
    
    assigned_officer_id = fields.Many2one('res.users', string='Assigned Communications Officer', tracking=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('comm_review', 'Communications Review'),
        ('consent_review', 'Safeguarding/Consent Review'),
        ('approved', 'Approved'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed or Published'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('revision', 'Revision Requested')
    ], string='Status', default='draft', tracking=True, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.media.request') or 'New'
        return super(MediaRequest, self).create(vals_list)
