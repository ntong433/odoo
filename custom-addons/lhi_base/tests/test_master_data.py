# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError
from odoo.tools import mute_logger

@tagged('post_install', '-at_install')
class TestLhiMasterData(TransactionCase):

    def setUp(self):
        super(TestLhiMasterData, self).setUp()
        self.office_model = self.env['lhi.office']
        self.dept_model = self.env['lhi.department']
        self.prog_model = self.env['lhi.programme']
        self.sector_model = self.env['lhi.sector']
        self.donor_model = self.env['lhi.donor']
        self.funding_model = self.env['lhi.funding.source']
        self.award_model = self.env['lhi.award']
        self.project_model = self.env['lhi.project']
        self.cc_model = self.env['lhi.cost.center']
        self.activity_model = self.env['lhi.activity']

    def test_01_office_creation_and_constraints(self):
        """Test Office creation, uniqueness of code, and date validations."""
        office = self.office_model.create({
            'name': 'Test Abuja Office',
            'code': 'OFF-ABJ-01',
            'office_type': 'head',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        })
        self.assertTrue(office.active)
        self.assertEqual(office.code, 'OFF-ABJ-01')

        # Test duplicate code raises unique constraint
        with self.cr.savepoint(), self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.office_model.create({
                'name': 'Duplicate Office',
                'code': 'OFF-ABJ-01',
            })

        # Test start_date > end_date raises ValidationError
        with self.assertRaises(ValidationError):
            self.office_model.create({
                'name': 'Bad Dates Office',
                'code': 'OFF-BAD',
                'start_date': '2026-12-31',
                'end_date': '2026-01-01',
            })

    def test_02_department_hierarchy(self):
        """Test Department creation and self-referencing parent/child structure."""
        parent_dept = self.dept_model.create({
            'name': 'Finance Department',
            'code': 'DEP-FIN',
        })
        child_dept = self.dept_model.create({
            'name': 'Logistics Unit',
            'code': 'UNT-LOG',
            'parent_id': parent_dept.id,
        })
        self.assertEqual(child_dept.parent_id.id, parent_dept.id)

    def test_03_programme_and_sectors(self):
        """Test programme sector association and integrity constraints."""
        prog = self.prog_model.create({
            'name': 'WASH Programme',
            'code': 'PRG-WASH',
        })
        sector = self.sector_model.create({
            'name': 'Water Supply Sector',
            'code': 'SEC-WASH-WS',
            'programme_id': prog.id,
        })
        self.assertEqual(sector.programme_id.id, prog.id)

    def test_04_donor_and_funding_source(self):
        """Test donor and funding source association."""
        donor = self.donor_model.create({
            'name': 'USAID BHA',
            'code': 'DNR-USAID',
            'donor_type': 'bilateral',
        })
        funding = self.funding_model.create({
            'name': 'BHA Emergency WASH 2026',
            'code': 'FND-BHA-26',
            'donor_id': donor.id,
        })
        self.assertEqual(funding.donor_id.id, donor.id)

    def test_05_award_and_project_auto_sequence(self):
        """Test Award and Project creation and auto-sequence code generation."""
        donor = self.donor_model.create({
            'name': 'USAID BHA',
            'code': 'DNR-USAID-SEQ',
        })
        funding = self.funding_model.create({
            'name': 'USAID Funding Seq',
            'code': 'FND-USAID-SEQ',
            'donor_id': donor.id,
        })
        
        # Creating award with default code '/' should invoke sequence
        award = self.award_model.create({
            'name': 'Test Sequence Award',
            'funding_source_id': funding.id,
        })
        self.assertNotEqual(award.code, '/')
        self.assertTrue(award.code.startswith('LHI/AWRD/'))

        # Creating project with default code '/' should invoke sequence
        project = self.project_model.create({
            'name': 'Test Sequence Project',
            'award_id': award.id,
        })
        self.assertNotEqual(project.code, '/')
        self.assertTrue(project.code.startswith('LHI/PROJ/'))

    def test_06_cost_center_and_activity(self):
        """Test Cost center and Activity models."""
        donor = self.donor_model.create({
            'name': 'Donor CC',
            'code': 'DNR-CC',
        })
        funding = self.funding_model.create({
            'name': 'Funding CC',
            'code': 'FND-CC',
            'donor_id': donor.id,
        })
        award = self.award_model.create({
            'name': 'Award CC',
            'funding_source_id': funding.id,
        })
        project = self.project_model.create({
            'name': 'Project CC',
            'award_id': award.id,
        })
        
        cc = self.cc_model.create({
            'name': 'Finance Cost Center',
            'code': 'CC-FIN-01',
            'project_id': project.id,
        })
        activity = self.activity_model.create({
            'name': 'Hygiene Kit Distribution',
            'code': 'ACT-HYG-01',
            'project_id': project.id,
            'output_code': 'OUT-1.1',
        })
        self.assertEqual(cc.project_id.id, project.id)
        self.assertEqual(activity.project_id.id, project.id)

    def test_07_unlink_constraints(self):
        """Test that active records and referenced records cannot be deleted, but inactive unreferenced records can."""
        office = self.office_model.create({
            'name': 'Test Abuja Office 2',
            'code': 'OFF-ABJ-02',
            'office_type': 'field',
        })
        with self.assertRaises(ValidationError):
            office.unlink()
        office.active = False
        child_office = self.office_model.create({
            'name': 'Sub Abuja Office',
            'code': 'OFF-SUB-02',
            'parent_id': office.id,
        })
        with self.assertRaises(ValidationError):
            office.unlink()
        child_office.active = False
        child_office.unlink()
        donor = self.donor_model.create({
            'name': 'Donor P1',
            'code': 'DNR-P1',
        })
        funding = self.funding_model.create({
            'name': 'Funding P1',
            'code': 'FND-P1',
            'donor_id': donor.id,
        })
        award = self.award_model.create({
            'name': 'Award P1',
            'funding_source_id': funding.id,
        })
        project = self.project_model.create({
            'name': 'Project P1',
            'award_id': award.id,
            'office_id': office.id,
        })
        with self.assertRaises(ValidationError):
            office.unlink()
        project.active = False
        project.unlink()
        office.unlink()
        self.assertFalse(office.exists())

    def test_08_security_permissions(self):
        """Test ACL permissions and record rules for LHI groups and multi-company settings."""
        company_2 = self.env['res.company'].create({'name': 'LHI Company 2'})
        
        user_lhi = self.env['res.users'].create({
            'name': 'LHI Standard User',
            'login': 'lhi_user_test',
            'email': 'lhi_user_test@lhinigeria.org',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [self.ref('lhi_security.group_lhi_user')])]
        })
        
        user_manager = self.env['res.users'].create({
            'name': 'LHI Manager User',
            'login': 'lhi_mgr_test',
            'email': 'lhi_mgr_test@lhinigeria.org',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [self.ref('lhi_security.group_lhi_manager')])]
        })

        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.office_model.with_user(user_lhi).create({
                'name': 'User office',
                'code': 'OFF-USR-1',
            })
            
        mgr_office = self.office_model.with_user(user_manager).create({
            'name': 'Manager office',
            'code': 'OFF-MGR-1',
            'company_id': self.env.company.id,
        })
        self.assertTrue(mgr_office)
        
        offices_for_user = self.office_model.with_user(user_lhi).search([('id', '=', mgr_office.id)])
        self.assertIn(mgr_office, offices_for_user)

        company2_office = self.office_model.create({
            'name': 'Company 2 office',
            'code': 'OFF-C2',
            'company_id': company_2.id,
        })
        
        all_offices = self.office_model.with_user(user_manager).search([])
        self.assertNotIn(company2_office, all_offices)

    def test_09_effective_date_controls(self):
        """Test the is_effective helper method and date range validity."""
        from datetime import date, timedelta
        today = date.today()
        
        # Office with no start/end date -> effective today
        office = self.office_model.create({
            'name': 'Date Office 1',
            'code': 'OFF-DATE-1',
        })
        self.assertTrue(office.is_effective())
        
        # Office with past date range -> not effective today
        office_past = self.office_model.create({
            'name': 'Date Office Past',
            'code': 'OFF-DATE-PAST',
            'start_date': today - timedelta(days=10),
            'end_date': today - timedelta(days=2),
        })
        self.assertFalse(office_past.is_effective())
        
        # Office with future date range -> not effective today
        office_future = self.office_model.create({
            'name': 'Date Office Future',
            'code': 'OFF-DATE-FUT',
            'start_date': today + timedelta(days=2),
            'end_date': today + timedelta(days=10),
        })
        self.assertFalse(office_future.is_effective())
        
        # Office within date range -> effective today
        office_current = self.office_model.create({
            'name': 'Date Office Current',
            'code': 'OFF-DATE-CUR',
            'start_date': today - timedelta(days=2),
            'end_date': today + timedelta(days=2),
        })
        self.assertTrue(office_current.is_effective())
