# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestLhiProjectWorkplan(common.TransactionCase):
    
    def setUp(self):
        super(TestLhiProjectWorkplan, self).setUp()
        self.project = self.env['lhi.project'].create({
            'name': 'Test Project',
            'code': 'TP-001',
        })
        self.odoo_project = self.env['project.project'].create({
            'name': 'Execution Project'
        })
        self.project.odoo_project_id = self.odoo_project.id
        
        self.workplan = self.env['lhi.workplan'].create({
            'name': 'Test Workplan',
            'project_id': self.project.id,
            'plan_type': 'annual',
            'start_date': '2030-01-01',
            'end_date': '2030-12-31'
        })
        
    def test_workplan_revision(self):
        """ Test that creating a revision increments version and sets parent """
        self.workplan.action_submit()
        self.workplan.action_approve()
        
        res = self.workplan.action_create_revision()
        new_plan = self.env['lhi.workplan'].browse(res['res_id'])
        
        self.assertEqual(self.workplan.state, 'revised')
        self.assertEqual(new_plan.state, 'draft')
        self.assertEqual(new_plan.version, 2)
        self.assertEqual(new_plan.parent_id.id, self.workplan.id)
        
    def test_activity_task_generation(self):
        """ Ensure approved activities can generate tasks """
        activity = self.env['lhi.workplan.activity'].create({
            'name': 'Test Activity',
            'workplan_id': self.workplan.id,
            'element_type': 'activity',
        })
        
        # Must be approved
        with self.assertRaises(ValidationError):
            activity.action_generate_task()
            
        activity.state = 'approved'
        activity.action_generate_task()
        
        self.assertTrue(activity.odoo_task_id)
        self.assertEqual(activity.odoo_task_id.project_id.id, self.odoo_project.id)
        self.assertEqual(activity.state, 'in_progress')
