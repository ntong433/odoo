# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

class LhiProposalAwardWizard(models.TransientModel):
    _name = 'lhi.proposal.award.wizard'
    _description = 'Proposal to Award Conversion Wizard'

    workspace_id = fields.Many2one('lhi.proposal.workspace', string='Workspace', required=True, readonly=True)
    submission_id = fields.Many2one('lhi.proposal.submission', string='Winning Submission', required=True, domain="[('workspace_id', '=', workspace_id)]")
    budget_id = fields.Many2one('lhi.proposal.budget', string='Approved Budget', required=True, domain="[('workspace_id', '=', workspace_id)]")
    
    award_name = fields.Char(string='Award Name', required=True)
    award_reference = fields.Char(string='Award Reference', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    def action_convert_to_award(self):
        self.ensure_one()
        
        # 1. Create the Grant/Award record
        award = self.env['lhi.award'].create({
            'name': self.award_name,
            'award_code': self.award_reference,
            'donor_id': self.workspace_id.donor_id.id,
            'funding_source_id': False, # Could be linked if standard
            'start_date': self.start_date,
            'end_date': self.end_date,
        })
        
        # 2. Create the internal Project
        project = self.env['lhi.project'].create({
            'name': self.award_name,
            'project_code': self.award_reference,
            'award_id': award.id,
            'programme_id': self.workspace_id.opportunity_id.programme_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'active': True,
        })
        
        # 3. Update Submission & Workspace status
        self.submission_id.state = 'awarded'
        
        # Optionally log the conversion on the workspace
        self.workspace_id.message_post(body=_("Proposal successfully converted to Award: %s (Project: %s)") % (award.name, project.name))
        
        # Return action to view the new award
        return {
            'name': 'Award',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.award',
            'res_id': award.id,
            'view_mode': 'form',
        }
