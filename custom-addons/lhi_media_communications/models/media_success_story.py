# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class MediaSuccessStory(models.Model):
    _name = 'lhi.media.success.story'
    _description = 'Media Success Story'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Story Title', required=True, tracking=True)
    
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    grant_id = fields.Many2one('lhi.grant.award', string='Grant/Donor')
    workplan_activity_id = fields.Many2one('lhi.workplan.activity', string='Workplan Activity')
    
    author_id = fields.Many2one('res.users', string='Author/Interviewer', default=lambda self: self.env.user)
    collection_date = fields.Date(string='Collection Date', default=fields.Date.context_today)
    location = fields.Char(string='Location')
    
    # Beneficiary Information (Sensitive - restrict via view access/groups if needed)
    beneficiary_name = fields.Char(string='Beneficiary Name or Approved Alias', required=True, tracking=True)
    age_group = fields.Selection([
        ('0-5', '0-5'),
        ('6-12', '6-12'),
        ('13-17', '13-17'),
        ('18-24', '18-24'),
        ('25-35', '25-35'),
        ('36-50', '36-50'),
        ('51+', '51+')
    ], string='Age Group')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')
    
    # Story Details
    situation_before = fields.Text(string='Situation Before Intervention')
    lhi_intervention = fields.Text(string='LHI Intervention')
    outcome_change = fields.Text(string='Outcome/Change', required=True)
    direct_quotation = fields.Text(string='Direct Quotation')
    quantitative_evidence = fields.Text(string='Quantitative Evidence')
    lessons_learned = fields.Text(string='Lessons Learned')
    
    # Media Attachments
    photo_ids = fields.Many2many('ir.attachment', 'story_photo_rel', string='Photos')
    video_ids = fields.Many2many('ir.attachment', 'story_video_rel', string='Videos')
    audio_ids = fields.Many2many('ir.attachment', 'story_audio_rel', string='Audio')
    
    # Consent and Compliance
    consent_form_id = fields.Many2one('ir.attachment', string='Consent Form')
    consent_status = fields.Selection([
        ('pending', 'Pending'),
        ('obtained', 'Obtained'),
        ('revoked', 'Revoked'),
        ('not_required', 'Not Required')
    ], string='Consent Status', default='pending', tracking=True, required=True)
    guardian_consent = fields.Boolean(string='Guardian Consent (If Minor)')
    anonymization_required = fields.Boolean(string='Anonymization Required')
    
    safeguarding_review = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Safeguarding Review', default='pending', tracking=True)
    
    communications_review = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Communications Review', default='pending', tracking=True)
    
    donor_approval = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Donor Approval', default='not_required', tracking=True)
    
    # Publication
    publication_channels = fields.Char(string='Publication Channels')
    publication_date = fields.Date(string='Publication Date')
    published_url = fields.Char(string='Published URL')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('consent_pending', 'Consent Pending'),
        ('safeguarding', 'Safeguarding Review'),
        ('communications', 'Communications Review'),
        ('donor_review', 'Donor Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)

    @api.constrains('state', 'consent_status', 'safeguarding_review', 'donor_approval')
    def _check_publication_requirements(self):
        for record in self:
            if record.state == 'published':
                if record.consent_status not in ['obtained', 'not_required']:
                    raise UserError("Cannot publish: Required consent is missing or revoked.")
                if record.safeguarding_review != 'approved':
                    raise UserError("Cannot publish: Safeguarding review is incomplete or rejected.")
                if record.donor_approval not in ['approved', 'not_required']:
                    raise UserError("Cannot publish: Required donor approval is missing or rejected.")
