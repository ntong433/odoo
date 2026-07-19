# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MediaActivity(models.Model):
    _name = 'lhi.media.activity'
    _description = 'Media Activity'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True, tracking=True)
    activity_type = fields.Selection([
        ('outreach', 'Outreach'),
        ('radio', 'Radio Programme'),
        ('event', 'Event Coverage'),
        ('photography', 'Photography'),
        ('video', 'Video Production'),
        ('interview', 'Interview'),
        ('press_release', 'Press Release'),
        ('newsletter', 'Newsletter'),
        ('social_media', 'Social Media Campaign'),
        ('iec', 'IEC Material'),
        ('success_story', 'Success Story Collection'),
        ('donor_visibility', 'Donor Visibility'),
        ('other', 'Other')
    ], string='Activity Type', required=True, tracking=True)

    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    workplan_activity_id = fields.Many2one('lhi.workplan.activity', string='Workplan Activity')
    task_id = fields.Many2one('project.task', string='Task')
    grant_id = fields.Many2one('lhi.award', string='Grant/Donor')
    
    owner_id = fields.Many2one('res.users', string='Owner', default=lambda self: self.env.user, tracking=True)
    team_member_ids = fields.Many2many('res.users', string='Team Members')
    
    start_date = fields.Datetime(string='Start Date and Time', required=True)
    end_date = fields.Datetime(string='End Date and Time')
    
    location = fields.Char(string='Location')
    state_id = fields.Many2one('res.country.state', string='State/LGA')
    
    target_audience = fields.Char(string='Target Audience')
    planned_reach = fields.Integer(string='Planned Reach')
    actual_reach = fields.Integer(string='Actual Reach', tracking=True)
    
    budget = fields.Float(string='Budget')
    actual_cost = fields.Float(string='Actual Cost', tracking=True)
    
    channels = fields.Char(string='Channels')
    
    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='planned', tracking=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    results = fields.Text(string='Results')
    lessons_learned = fields.Text(string='Lessons Learned')
    follow_up_actions = fields.Text(string='Follow-up Actions')

    # Radio Programme specific fields
    radio_station = fields.Char(string='Radio Station')
    programme_name = fields.Char(string='Programme Name')
    episode_title = fields.Char(string='Episode Title/Number')
    broadcast_date = fields.Datetime(string='Broadcast Date and Time')
    duration = fields.Float(string='Duration (Minutes)')
    language = fields.Char(string='Language')
    topic = fields.Char(string='Topic')
    presenter = fields.Char(string='Presenter')
    guests = fields.Char(string='Guests')
    estimated_audience = fields.Integer(string='Estimated Audience')
    call_ins = fields.Integer(string='Call-ins')
    questions_received = fields.Text(string='Questions Received')
    listener_feedback = fields.Text(string='Listener Feedback')
    recording = fields.Binary(string='Recording')
    broadcast_cost = fields.Float(string='Broadcast Cost')
    repeat_broadcast = fields.Boolean(string='Repeat Broadcast')
    radio_outcome = fields.Text(string='Outcome')

    # Outreach specific fields
    outreach_objective = fields.Text(string='Objective')
    outreach_community = fields.Char(string='Community/Location')
    outreach_target_population = fields.Char(string='Target Population')
    outreach_key_messages = fields.Text(string='Key Messages')
    outreach_partners = fields.Char(string='Partners')
    outreach_materials_distributed = fields.Text(string='Materials Distributed')
    outreach_planned_participants = fields.Integer(string='Planned Participants')
    outreach_actual_participants = fields.Integer(string='Actual Participants')
    outreach_female = fields.Integer(string='Female')
    outreach_male = fields.Integer(string='Male')
    outreach_pwd = fields.Integer(string='Persons with Disabilities')
    outreach_children_youth = fields.Integer(string='Children/Youth')
    outreach_leaders = fields.Integer(string='Community Leaders')
    outreach_referrals = fields.Integer(string='Referrals Made')
    outreach_questions = fields.Text(string='Questions and Feedback')
    outreach_evidence_ids = fields.Many2many('ir.attachment', 'media_outreach_evidence_rel', string='Evidence Attachments')
    outreach_follow_up = fields.Boolean(string='Follow-up Required')
