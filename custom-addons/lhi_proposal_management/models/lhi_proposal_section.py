# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProposalSectionTemplate(models.Model):
    _name = 'lhi.proposal.section.template'
    _description = 'Proposal Section Template'
    _order = 'sequence'

    name = fields.Char(string='Section Name', required=True)
    section_type = fields.Selection([
        ('technical', 'Technical Narrative'),
        ('toc', 'Theory of Change'),
        ('objectives', 'Objectives & Outcomes'),
        ('activities', 'Activities & Implementation'),
        ('workplan', 'Work Plan'),
        ('meal', 'MEAL Framework'),
        ('risk', 'Risk Register'),
        ('sustainability', 'Sustainability & Safeguarding'),
        ('staffing', 'Staffing & HR'),
        ('procurement', 'Procurement Plan'),
        ('budget', 'Budget Narrative'),
        ('other', 'Other')
    ], string='Section Type', required=True)
    workspace_type = fields.Selection([
        ('concept_note', 'Concept Note Only'),
        ('full_proposal', 'Full Proposal Only'),
        ('both', 'Both')
    ], string='Applies To', default='both')
    required = fields.Boolean(string='Required for Submission', default=True)
    sequence = fields.Integer(default=10)


class LhiProposalSection(models.Model):
    _name = 'lhi.proposal.section'
    _description = 'Proposal Section'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'workspace_id, sequence, id'

    name = fields.Char(string='Section Name', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    workspace_id = fields.Many2one('lhi.proposal.workspace', string='Workspace', required=True, ondelete='cascade')
    
    section_type = fields.Selection(related='template_id.section_type', readonly=False, store=True)
    template_id = fields.Many2one('lhi.proposal.section.template', string='Template')
    
    required = fields.Boolean(string='Required', default=True)

    state = fields.Selection([
        ('draft', 'Drafting'),
        ('review', 'In Review'),
        ('revision', 'Needs Revision'),
        ('approved', 'Approved')
    ], string='Status', default='draft', required=True, tracking=True)

    owner_id = fields.Many2one('res.users', string='Section Owner (Writer)', required=True, tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Reviewer', tracking=True)
    contributor_ids = fields.Many2many('res.users', string='Contributors')

    deadline = fields.Date(string='Internal Section Deadline', tracking=True)
    content = fields.Html(string='Content Draft', tracking=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    def action_submit_review(self):
        self.ensure_one()
        if not self.reviewer_id:
            raise ValidationError(_("Please assign a reviewer before submitting for review."))
        self.state = 'review'
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.reviewer_id.id,
            summary=_('Review Requested: %s') % self.name
        )

    def action_approve(self):
        self.ensure_one()
        self.state = 'approved'

    def action_request_revision(self):
        self.ensure_one()
        self.state = 'revision'
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.owner_id.id,
            summary=_('Revision Requested: %s') % self.name
        )
