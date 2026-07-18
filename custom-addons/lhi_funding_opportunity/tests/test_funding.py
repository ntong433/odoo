# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiFundingOpportunity(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiFundingOpportunity, self).setUp()
        self.Opportunity = self.env['lhi.funding.opportunity']
        self.Stage = self.env['lhi.funding.stage']
        
        # Create a dummy donor
        self.donor = self.env['lhi.donor'].create({
            'name': 'Test Donor',
            'code': 'TD-001',
            'donor_type': 'ngo'
        })
        
        # Create stage
        self.stage_new = self.Stage.create({'name': 'New', 'sequence': 1})
        self.stage_won = self.Stage.create({'name': 'Won', 'sequence': 5, 'is_won': True})
        
    def test_opportunity_creation(self):
        """ Test creating an opportunity calculates score correctly """
        opp = self.Opportunity.create({
            'name': 'Test Opportunity',
            'donor_id': self.donor.id,
            'submission_deadline': '2030-01-01',
            'score_strategic_fit': 8,
            'score_technical_capacity': 7
        })
        
        self.assertEqual(opp.total_score, 15, "Total score should be calculated from individual scores")
        
    def test_donor_opportunity_count(self):
        """ Test that the donor reflects the correct number of opportunities """
        self.Opportunity.create({
            'name': 'Opp 1',
            'donor_id': self.donor.id,
            'submission_deadline': '2030-01-01'
        })
        self.Opportunity.create({
            'name': 'Opp 2',
            'donor_id': self.donor.id,
            'submission_deadline': '2030-01-01'
        })
        
        self.assertEqual(self.donor.opportunity_count, 2, "Donor should have 2 opportunities linked")

    def test_pipeline_action_uses_odoo_19_card_kanban(self):
        action = self.env.ref(
            'lhi_funding_opportunity.action_lhi_funding_opportunity'
        )
        kanban_view = self.env.ref(
            'lhi_funding_opportunity.view_lhi_funding_opportunity_kanban'
        )
        combined_arch = str(kanban_view.get_combined_arch())

        self.assertIn('t-name="card"', combined_arch)
        self.assertNotIn('t-name="kanban-box"', combined_arch)
        self.assertIn('lhi-pipeline-kanban-card', combined_arch)
        self.assertEqual(action.views[0], (kanban_view.id, 'kanban'))
