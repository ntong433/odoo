# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiProposalManagement(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiProposalManagement, self).setUp()
        
        self.donor = self.env['lhi.donor'].create({
            'name': 'Proposal Donor',
            'code': 'PD-001',
            'donor_type': 'ngo'
        })
        
        self.opportunity = self.env['lhi.funding.opportunity'].create({
            'name': 'Test Opp',
            'donor_id': self.donor.id,
            'submission_deadline': '2030-01-01'
        })
        
    def test_workspace_creation(self):
        """ Test workspace creation auto-generates templates (assuming data is loaded) """
        workspace = self.env['lhi.proposal.workspace'].create({
            'name': 'Concept Note WS',
            'opportunity_id': self.opportunity.id,
            'workspace_type': 'concept_note',
            'deadline': '2029-12-01'
        })
        
        self.assertEqual(workspace.state, 'draft', "Workspace should start in draft state")
        
    def test_workspace_constraints(self):
        """ Internal deadline cannot be past final submission deadline """
        with self.assertRaises(ValidationError):
            self.env['lhi.proposal.workspace'].create({
                'name': 'Concept Note WS 2',
                'opportunity_id': self.opportunity.id,
                'workspace_type': 'concept_note',
                'deadline': '2030-02-01' # Past the opp submission_deadline of 2030-01-01
            })
