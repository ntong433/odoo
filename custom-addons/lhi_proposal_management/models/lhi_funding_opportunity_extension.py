# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

class LhiFundingOpportunity(models.Model):
    _inherit = 'lhi.funding.opportunity'

    workspace_count = fields.Integer(string='Workspaces', compute='_compute_workspace_count')

    def _compute_workspace_count(self):
        for record in self:
            record.workspace_count = self.env['lhi.proposal.workspace'].search_count([
                ('opportunity_id', '=', record.id)
            ])

    def action_create_concept_note(self):
        self.ensure_one()
        return self._create_workspace('concept_note', _('Concept Note'))

    def action_create_full_proposal(self):
        self.ensure_one()
        return self._create_workspace('full_proposal', _('Full Proposal'))

    def _create_workspace(self, wtype, wtitle):
        if self.approval_request_id and self.approval_request_id.state != 'approved':
            raise ValidationError(_("Cannot create a workspace unless the Go/No-Go approval is approved."))
        
        workspace = self.env['lhi.proposal.workspace'].create({
            'name': f"{self.name} - {wtitle}",
            'opportunity_id': self.id,
            'workspace_type': wtype,
            'lead_writer_id': self.user_id.id,
            'deadline': self.submission_deadline,
        })
        workspace._generate_default_sections()
        
        return {
            'name': wtitle,
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.workspace',
            'res_id': workspace.id,
            'view_mode': 'form',
        }

    def action_view_workspaces(self):
        self.ensure_one()
        return {
            'name': 'Workspaces',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.proposal.workspace',
            'view_mode': 'list,form',
            'domain': [('opportunity_id', '=', self.id)],
            'context': {'default_opportunity_id': self.id}
        }
