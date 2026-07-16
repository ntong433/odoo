# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiProposalBudget(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiProposalBudget, self).setUp()
        
        self.donor = self.env['lhi.donor'].create({
            'name': 'Budget Donor',
            'code': 'BD-001',
            'donor_type': 'ngo'
        })
        
        self.opportunity = self.env['lhi.funding.opportunity'].create({
            'name': 'Budget Opp',
            'donor_id': self.donor.id,
            'submission_deadline': '2030-01-01',
            'funding_ceiling': 1000.0,
        })
        
        self.workspace = self.env['lhi.proposal.workspace'].create({
            'name': 'Budget WS',
            'opportunity_id': self.opportunity.id,
            'workspace_type': 'full_proposal',
            'deadline': '2029-12-01'
        })
        
        self.location = self.env['lhi.office'].create({'name': 'HQ'})
        self.department = self.env['lhi.department'].create({'name': 'Health'})
        self.cost_center = self.env['lhi.cost.center'].create({'name': 'CC-01'})
        self.currency = self.env.ref('base.USD')
        
    def test_budget_calculations(self):
        """ Test unit cost calculation and percentage split """
        budget = self.env['lhi.proposal.budget'].create({
            'name': 'Test Budget',
            'workspace_id': self.workspace.id,
        })
        
        line = self.env['lhi.proposal.budget.line'].create({
            'budget_id': budget.id,
            'donor_category': 'Personnel',
            'lhi_category': 'Staff',
            'location_id': self.location.id,
            'department_id': self.department.id,
            'cost_center_id': self.cost_center.id,
            'unit': 'Months',
            'unit_cost': 100.0,
            'quantity': 1.0,
            'frequency': 1.0,
            'duration': 5.0,
            'currency_id': self.currency.id,
            'exchange_rate': 1.0,
            'donor_percentage': 80.0,
            'lhi_percentage': 20.0,
            'partner_percentage': 0.0,
        })
        
        self.assertEqual(line.line_total, 500.0)
        self.assertEqual(line.donor_contribution_base, 400.0)
        self.assertEqual(line.lhi_contribution_base, 100.0)
        
        self.assertEqual(budget.total_donor_contribution, 400.0)
        self.assertEqual(budget.total_lhi_contribution, 100.0)
        self.assertEqual(budget.total_amount, 500.0)

    def test_budget_percentage_validation(self):
        """ Percentages must equal 100% """
        budget = self.env['lhi.proposal.budget'].create({
            'name': 'Test Budget',
            'workspace_id': self.workspace.id,
        })
        
        with self.assertRaises(ValidationError):
            self.env['lhi.proposal.budget.line'].create({
                'budget_id': budget.id,
                'donor_category': 'Travel',
                'lhi_category': 'Flights',
                'location_id': self.location.id,
                'department_id': self.department.id,
                'cost_center_id': self.cost_center.id,
                'unit': 'Trips',
                'donor_percentage': 50.0,
                'lhi_percentage': 30.0,
                'partner_percentage': 10.0, # Equals 90%
                'currency_id': self.currency.id,
            })
            
    def test_budget_ceiling_validation(self):
        """ Ensure budget doesn't exceed funding ceiling of 1000 """
        budget = self.env['lhi.proposal.budget'].create({
            'name': 'Test Budget',
            'workspace_id': self.workspace.id,
        })
        
        with self.assertRaises(ValidationError):
            self.env['lhi.proposal.budget.line'].create({
                'budget_id': budget.id,
                'donor_category': 'Equipment',
                'lhi_category': 'Laptops',
                'location_id': self.location.id,
                'department_id': self.department.id,
                'cost_center_id': self.cost_center.id,
                'unit': 'Item',
                'unit_cost': 1500.0,
                'quantity': 1.0,
                'currency_id': self.currency.id,
                'donor_percentage': 100.0,
                'lhi_percentage': 0.0,
                'partner_percentage': 0.0,
            })
