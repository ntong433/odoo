# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestLhiSecurityRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestLhiSecurityRules, cls).setUpClass()
        
        # Setup groups
        cls.group_user = cls.env.ref('lhi_security.group_lhi_user')
        cls.group_employee = cls.env.ref('lhi_security.group_lhi_employee')
        cls.group_manager = cls.env.ref('lhi_security.group_lhi_manager')
        cls.group_erp_admin = cls.env.ref('lhi_security.group_lhi_erp_admin')
        cls.group_programme_viewer = cls.env.ref('lhi_security.group_lhi_programme_viewer')
        cls.group_project_manager = cls.env.ref('lhi_security.group_lhi_project_manager')

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
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_programme_viewer.id])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'LHI Test Manager',
            'login': 'lhi_manager',
            'email': 'mgr@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_manager.id, cls.group_project_manager.id])],
        })

    def test_00_erp_administrator_inherits_manager_and_employee(self):
        """Protected ERP administrators inherit both organization-wide roles."""
        administrator = self.env.ref('base.user_admin')

        self.assertTrue(administrator.has_group('lhi_security.group_lhi_erp_admin'))
        self.assertTrue(administrator.has_group('lhi_security.group_lhi_manager'))
        self.assertTrue(administrator.has_group('lhi_security.group_lhi_employee'))
        self.assertIn(self.group_manager, self.group_erp_admin.implied_ids)
        self.assertIn(self.group_employee, self.group_erp_admin.implied_ids)

    def test_00_ordinary_employee_and_manager_hierarchy_is_unchanged(self):
        """The ERP-admin fix does not broaden ordinary employee or manager roles."""
        manager_only = self.env['res.users'].create({
            'name': 'LHI Manager Only',
            'login': 'lhi_manager_only',
            'email': 'manager.only@lhinigeria.org',
            'group_ids': [(6, 0, [self.group_manager.id])],
        })

        self.assertTrue(self.user_employee.has_group('lhi_security.group_lhi_employee'))
        self.assertFalse(self.user_employee.has_group('lhi_security.group_lhi_manager'))
        self.assertTrue(manager_only.has_group('lhi_security.group_lhi_manager'))
        self.assertFalse(manager_only.has_group('lhi_security.group_lhi_employee'))
        self.assertIn(self.group_user, self.group_employee.implied_ids)
        self.assertIn(self.group_user, self.group_manager.implied_ids)
        self.assertNotIn(self.group_employee, self.group_manager.implied_ids)
        self.assertNotIn(self.group_manager, self.group_employee.implied_ids)

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

    def test_06_category_name_xml_safety(self):
        """Custom ir.module.category display names must not contain unsafe XML characters (&, <, >)."""
        categories = self.env["ir.module.category"].sudo().search([])
        custom_categories = categories.filtered(
            lambda c: c.xml_id and (c.xml_id.startswith("lhi_") or c.xml_id.startswith("module_category_lhi_"))
        )
        unsafe_categories = custom_categories.filtered(
            lambda c: any(char in (c.name or "") for char in "&<>")
        )
        self.assertFalse(
            unsafe_categories,
            f"Unsafe characters found in categories: {[c.name for c in unsafe_categories]}"
        )

    def test_07_privilege_name_xml_safety(self):
        """Custom res.groups.privilege display names and placeholders must not contain unsafe XML characters."""
        privileges = self.env["res.groups.privilege"].sudo().search([])
        unsafe_privileges = privileges.filtered(
            lambda p: any(char in (p.name or "") for char in "&<>") or any(char in (p.placeholder or "") for char in "&<>")
        )
        self.assertFalse(
            unsafe_privileges,
            f"Unsafe characters found in privileges: {[p.name for p in unsafe_privileges]}"
        )

    def test_08_admin_and_warehouse_officer_rbac_regressions(self):
        """Verify ERP Admin access and Warehouse Officer entitlement boundaries."""
        admin_user = self.env.ref("base.user_admin")
        self.assertTrue(admin_user.has_lhi_app_access("operations"))
        self.assertTrue(admin_user.has_lhi_app_access("hub"))
        self.assertTrue(admin_user.has_lhi_app_access("programs_grants"))
        self.assertTrue(admin_user.has_lhi_app_access("memo"))

        warehouse_group = self.env.ref("lhi_security.group_lhi_warehouse_officer")
        test_warehouse_user = self.env["res.users"].create({
            "name": "James Bassey Test",
            "login": "jbassey_test",
            "email": "jbassey_test@example.com",
            "groups_id": [(6, 0, [warehouse_group.id])],
        })
        self.assertTrue(test_warehouse_user.has_lhi_app_access("hub"))
        self.assertTrue(test_warehouse_user.has_lhi_app_access("memo"))
        self.assertFalse(test_warehouse_user.has_lhi_app_access("operations"))
        self.assertFalse(test_warehouse_user.has_lhi_app_access("programs_grants"))

