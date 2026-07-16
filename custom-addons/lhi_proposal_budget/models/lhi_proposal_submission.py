# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiProposalSubmission(models.Model):
    _name = 'lhi.proposal.submission'
    _description = 'Proposal Submission Version'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Submission Reference', required=True, readonly=True, default=lambda self: _('New'))
    workspace_id = fields.Many2one('lhi.proposal.workspace', string='Proposal Workspace', required=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one(related='workspace_id.company_id', store=True)

    submission_date = fields.Date(string='Submission Date', required=True, default=fields.Date.context_today)
    submission_method = fields.Selection([
        ('email', 'Email'),
        ('portal', 'Donor Portal'),
        ('physical', 'Physical Delivery'),
        ('other', 'Other')
    ], string='Submission Method', required=True)
    
    # Immutable Snapshots
    narrative_snapshot = fields.Binary(string='Narrative Snapshot (PDF)', attachment=True)
    budget_snapshot = fields.Binary(string='Budget Snapshot (Excel/PDF)', attachment=True)
    annexes_snapshot = fields.Many2many('ir.attachment', string='Annexes Snapshot')
    
    acknowledgement_received = fields.Boolean(string='Acknowledgement Received', default=False)
    
    state = fields.Selection([
        ('submitted', 'Submitted'),
        ('clarification', 'Clarification Requested'),
        ('revised', 'Revised (Superseded)'),
        ('awarded', 'Awarded'),
        ('rejected', 'Rejected')
    ], string='Status', default='submitted', tracking=True)

    clarification_ids = fields.One2many('lhi.proposal.clarification', 'submission_id', string='Clarifications')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.proposal.submission') or _('New')
        return super(LhiProposalSubmission, self).create(vals_list)

class LhiProposalClarification(models.Model):
    _name = 'lhi.proposal.clarification'
    _description = 'Donor Clarification'

    submission_id = fields.Many2one('lhi.proposal.submission', string='Submission Version', required=True, ondelete='cascade')
    date_received = fields.Date(string='Date Received', required=True, default=fields.Date.context_today)
    deadline = fields.Date(string='Response Deadline', required=True)
    
    question = fields.Text(string='Donor Query / Comment', required=True)
    response = fields.Text(string='LHI Response')
    
    status = fields.Selection([
        ('open', 'Open'),
        ('responded', 'Responded')
    ], string='Status', default='open')
