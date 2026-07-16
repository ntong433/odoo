# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiProjectCompliance(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiProjectCompliance, self).setUp()
        self.project = self.env['lhi.project'].create({
            'name': 'Test Project',
            'code': 'TP-001',
        })
        self.user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser_compliance',
        })
        
    def test_activation_blocked(self):
        """ Ensure project activation fails if checklist is incomplete """
        self.project.state = 'setup'
        with self.assertRaises(ValidationError):
            self.project.action_activate_project()
            
    def test_activation_success(self):
        """ Ensure project activation succeeds when checklist is complete """
        self.project.write({
            'chk_signed_agreement': True,
            'chk_approved_budget': True,
            'chk_workplan': True,
            'chk_project_team': True,
            'chk_project_code': True,
            'chk_procurement_plan': True,
            'chk_meal_setup': True,
            'chk_risk_register': True,
            'chk_reporting_calendar': True,
            'focal_pm_id': self.user.id,
            'focal_finance_id': self.user.id,
            'focal_meal_id': self.user.id,
        })
        
        # This should trigger onchange or manual true for focal persons
        self.project.chk_focal_persons = True
        
        self.project.action_activate_project()
        self.assertEqual(self.project.state, 'active')
        self.assertTrue(self.project.active)
