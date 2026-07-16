# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiProposalAnnex(models.Model):
    _name = 'lhi.proposal.annex'
    _description = 'Proposal Annex Checklist'
    _order = 'workspace_id, id'

    name = fields.Char(string='Annex / Document Name', required=True)
    workspace_id = fields.Many2one('lhi.proposal.workspace', string='Workspace', required=True, ondelete='cascade')
    
    required = fields.Boolean(string='Required for Submission', default=True)
    is_completed = fields.Boolean(string='Completed', default=False)
    
    attachment_id = fields.Many2one('ir.attachment', string='Final Document')
    notes = fields.Text(string='Notes')
