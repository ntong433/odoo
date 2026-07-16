# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

class LhiProposalWorkspace(models.Model):
    _inherit = 'lhi.proposal.workspace'

    budget_ids = fields.One2many('lhi.proposal.budget', 'workspace_id', string='Budgets')
    submission_ids = fields.One2many('lhi.proposal.submission', 'workspace_id', string='Submissions')

    def action_view_budgets(self):
        self.ensure_one()
        return {
            'name': 'Budgets',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.budget',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.id)],
            'context': {'default_workspace_id': self.id}
        }

    def action_view_submissions(self):
        self.ensure_one()
        return {
            'name': 'Submissions',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.submission',
            'view_mode': 'list,form',
            'domain': [('workspace_id', '=', self.id)],
            'context': {'default_workspace_id': self.id}
        }

    def action_create_submission(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_("You can only create a submission package for approved workspaces."))
        
        return {
            'name': 'New Submission Package',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.submission',
            'view_mode': 'form',
            'context': {'default_workspace_id': self.id}
        }

    def action_launch_award_wizard(self):
        self.ensure_one()
        if not self.submission_ids.filtered(lambda s: s.state == 'awarded'):
            # It's better to enforce award state on submission, but for wizard we just launch
            pass

        return {
            'name': 'Convert to Award',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.award.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workspace_id': self.id}
        }
