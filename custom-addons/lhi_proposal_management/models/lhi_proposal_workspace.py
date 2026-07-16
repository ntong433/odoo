# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProposalWorkspace(models.Model):
    _name = 'lhi.proposal.workspace'
    _description = 'Proposal Workspace'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Workspace Title', required=True, tracking=True)
    opportunity_id = fields.Many2one('lhi.funding.opportunity', string='Funding Opportunity', required=True, tracking=True)
    donor_id = fields.Many2one(related='opportunity_id.donor_id', string='Donor', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    workspace_type = fields.Selection([
        ('concept_note', 'Concept Note'),
        ('full_proposal', 'Full Proposal')
    ], string='Type', default='full_proposal', required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Drafting'),
        ('review', 'Internal Review'),
        ('approved', 'Approved for Submission'),
        ('submitted', 'Submitted')
    ], string='Status', default='draft', required=True, tracking=True)

    lead_writer_id = fields.Many2one('res.users', string='Lead Writer / Owner', required=True, default=lambda self: self.env.user, tracking=True)
    deadline = fields.Date(string='Internal Deadline', required=True, tracking=True)
    submission_deadline = fields.Date(related='opportunity_id.submission_deadline', string='Final Submission Deadline', readonly=True)

    section_ids = fields.One2many('lhi.proposal.section', 'workspace_id', string='Proposal Sections')
    annex_ids = fields.One2many('lhi.proposal.annex', 'workspace_id', string='Annexes & Checklists')
    
    approval_request_id = fields.Many2one('lhi.approval.request', string='Final Approval Request', readonly=True, copy=False)

    @api.constrains('deadline', 'submission_deadline')
    def _check_deadline(self):
        for record in self:
            if record.deadline and record.submission_deadline and record.deadline > record.submission_deadline:
                raise ValidationError(_("Internal deadline cannot be later than the donor's submission deadline."))

    def action_submit_for_review(self):
        for record in self:
            # Check if all mandatory sections are completed
            incomplete_sections = record.section_ids.filtered(lambda s: s.required and s.state != 'approved')
            if incomplete_sections:
                raise ValidationError(_("Cannot submit for review. The following mandatory sections are not approved:\n%s") % '\n'.join(incomplete_sections.mapped('name')))
            
            record.state = 'review'

    def action_request_final_approval(self):
        self.ensure_one()
        if self.state != 'review':
            raise ValidationError(_("You can only request final approval from the Internal Review state."))
            
        incomplete_annexes = self.annex_ids.filtered(lambda a: a.required and not a.is_completed)
        if incomplete_annexes:
            raise ValidationError(_("Cannot request final approval. The following required annexes are incomplete:\n%s") % '\n'.join(incomplete_annexes.mapped('name')))

        matrix = self.env['lhi.approval.matrix'].search([
            ('model_name', '=', 'lhi.proposal.workspace'),
            ('active', '=', True)
        ], limit=1)
        
        if not matrix:
            raise ValidationError(_("No active approval matrix found for Proposal Workspaces. Please configure one."))
            
        approval = self.env['lhi.approval.request'].create({
            'matrix_id': matrix.id,
            'res_model': 'lhi.proposal.workspace',
            'res_id': self.id,
            'reference': f"Final Approval: {self.name}",
            'requester_id': self.env.user.id,
        })
        
        approval.action_submit()
        self.approval_request_id = approval.id
        self.message_post(body=_("Final Approval Request %s submitted.") % approval.name)

    def action_mark_approved(self):
        # Typically called by the approval engine callback or manually by superusers
        for record in self:
            record.state = 'approved'

    def action_mark_submitted(self):
        for record in self:
            if record.state != 'approved':
                raise ValidationError(_("Only approved proposals can be marked as submitted."))
            record.state = 'submitted'
            
    def _generate_default_sections(self):
        """ Can be called to auto-populate default sections """
        self.ensure_one()
        templates = self.env['lhi.proposal.section.template'].search([('workspace_type', 'in', [self.workspace_type, 'both'])])
        for tmpl in templates:
            self.env['lhi.proposal.section'].create({
                'workspace_id': self.id,
                'name': tmpl.name,
                'section_type': tmpl.section_type,
                'required': tmpl.required,
                'owner_id': self.lead_writer_id.id,
                'deadline': self.deadline,
            })
