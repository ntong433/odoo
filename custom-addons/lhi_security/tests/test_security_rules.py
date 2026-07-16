# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError

@tagged('post_install', '-at_install')
class TestLhiSecurityRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestLhiSecurityRules, cls).setUpClass()
        
        # Setup groups
        cls.group_employee = cls.env.ref('lhi_security.group_lhi_employee')
        cls.group_manager = cls.env.ref('lhi_security.group_lhi_manager')

        # Setup standard company
        cls.company = cls.env.company

        # Setup departments
        cls.dept_hq = cls.env['lhi.department'].create({
            'name': 'Headquarters Department',
            'code': 'HQ-DEPT',
            'company_id': cls.company.id,
        })
        cls.dept_finance = cls.env['lhi.department'].create({
            'name': 'Finance Department',
            'code': 'FIN-DEPT',
            'parent_id': cls.dept_hq.id,
            'company_id': cls.company.id,
        })
        cls.dept_hr = cls.env['lhi.department'].create({
            'name': 'HR Department',
            'code': 'HR-DEPT',
            'company_id': cls.company.id,
        })

        # Setup offices
        cls.office_main = cls.env['lhi.office'].create({
            'name': 'Main Office',
            'code': 'MO-OFF',
            'office_type': 'head',
            'company_id': cls.company.id,
        })
        cls.office_field = cls.env['lhi.office'].create({
            'name': 'Field Office A',
            'code': 'FOA-OFF',
            'office_type': 'field',
            'parent_id': cls.office_main.id,
            'company_id': cls.company.id,
        })
        cls.office_other = cls.env['lhi.office'].create({
            'name': 'Field Office B',
            'code': 'FOB-OFF',
            'office_type': 'field',
            'company_id': cls.company.id,
        })

        # Setup projects
        cls.project_a = cls.env['lhi.project'].create({
            'name': 'Project Alpha',
            'code': 'PRJ-ALP',
            'office_id': cls.office_field.id,
            'company_id': cls.company.id,
        })
        cls.project_b = cls.env['lhi.project'].create({
            'name': 'Project Beta',
            'code': 'PRJ-BET',
            'office_id': cls.office_other.id,
            'company_id': cls.company.id,
        })

        # Create test users
        cls.user_employee = cls.env['res.users'].create({
            'name': 'LHI Test Employee',
            'login': 'lhi_employee',
            'email': 'emp@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'LHI Test Manager',
            'login': 'lhi_manager',
            'email': 'mgr@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_manager.id])],
        })

    def test_01_no_restrictions_employee(self):
        """When an employee has no restrictions set, they can see all records."""
        # Authenticate as employee
        employee_env = self.env(user=self.user_employee)
        
        # Should be able to read all departments, offices, projects
        depts = employee_env['lhi.department'].search([])
        offices = employee_env['lhi.office'].search([])
        projects = employee_env['lhi.project'].search([])
        
        self.assertIn(self.dept_hr.id, depts.ids)
        self.assertIn(self.dept_finance.id, depts.ids)
        self.assertIn(self.office_field.id, offices.ids)
        self.assertIn(self.office_other.id, offices.ids)
        self.assertIn(self.project_a.id, projects.ids)
        self.assertIn(self.project_b.id, projects.ids)

    def test_02_department_restriction(self):
        """Restricting an employee to a parent department allows access to it and child departments, but blocks others."""
        self.user_employee.write({
            'lhi_department_ids': [(6, 0, [self.dept_hq.id])]
        })
        
        employee_env = self.env(user=self.user_employee)
        
        # Search departments as restricted user
        depts = employee_env['lhi.department'].search([])
        self.assertIn(self.dept_hq.id, depts.ids, "Restricted user should see HQ")
        self.assertIn(self.dept_finance.id, depts.ids, "Restricted user should see child dept (Finance)")
        self.assertNotIn(self.dept_hr.id, depts.ids, "Restricted user should NOT see HR")

    def test_03_project_restriction(self):
        """Restricting an employee to a specific project blocks access to other projects."""
        self.user_employee.write({
            'lhi_project_ids': [(6, 0, [self.project_a.id])]
        })
        
        employee_env = self.env(user=self.user_employee)
        
        projects = employee_env['lhi.project'].search([])
        self.assertIn(self.project_a.id, projects.ids, "Restricted user should see Project Alpha")
        self.assertNotIn(self.project_b.id, projects.ids, "Restricted user should NOT see Project Beta")

    def test_04_office_restriction(self):
        """Restricting an employee to a parent office propagates to child offices, but blocks others."""
        self.user_employee.write({
            'lhi_office_ids': [(6, 0, [self.office_main.id])]
        })
        
        employee_env = self.env(user=self.user_employee)
        
        offices = employee_env['lhi.office'].search([])
        self.assertIn(self.office_main.id, offices.ids, "Restricted user should see Main Office")
        self.assertIn(self.office_field.id, offices.ids, "Restricted user should see child office")
        self.assertNotIn(self.office_other.id, offices.ids, "Restricted user should NOT see Field Office B")

    def test_05_manager_bypass(self):
        """Managers bypass all restrictions even if department/project/office list is configured on their user."""
        self.user_manager.write({
            'lhi_department_ids': [(6, 0, [self.dept_hr.id])],
            'lhi_project_ids': [(6, 0, [self.project_b.id])],
            'lhi_office_ids': [(6, 0, [self.office_other.id])],
        })
        
        manager_env = self.env(user=self.user_manager)
        
        depts = manager_env['lhi.department'].search([])
        offices = manager_env['lhi.office'].search([])
        projects = manager_env['lhi.project'].search([])
        
        self.assertIn(self.dept_hq.id, depts.ids, "Manager bypass should allow seeing HQ")
        self.assertIn(self.dept_finance.id, depts.ids, "Manager bypass should allow seeing Finance")
        self.assertIn(self.office_main.id, offices.ids, "Manager bypass should allow seeing Main Office")
        self.assertIn(self.project_a.id, projects.ids, "Manager bypass should allow seeing Project Alpha")
