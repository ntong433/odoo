# -*- coding: utf-8 -*-
from odoo.tests import common

class TestLhiProjectLifecycle(common.TransactionCase):
    
    def test_odoo_project_creation(self):
        """ Ensure activating a project automatically creates an Odoo project """
        user = self.env['res.users'].create({
            'name': 'PM User',
            'login': 'pm_user_lifecycle',
        })
        
        project = self.env['lhi.project'].create({
            'name': 'Lifecycle Project',
            'code': 'LC-001',
            'focal_pm_id': user.id,
            'focal_finance_id': user.id,
            'focal_meal_id': user.id,
            'chk_signed_agreement': True,
            'chk_approved_budget': True,
            'chk_workplan': True,
            'chk_project_team': True,
            'chk_project_code': True,
            'chk_procurement_plan': True,
            'chk_meal_setup': True,
            'chk_risk_register': True,
            'chk_reporting_calendar': True,
            'chk_focal_persons': True,
        })
        
        # Activate project
        project.action_activate_project()
        
        self.assertTrue(project.odoo_project_id)
        self.assertEqual(project.odoo_project_id.name, '[LC-001] Lifecycle Project')
        self.assertEqual(project.odoo_project_id.user_id.id, user.id)
