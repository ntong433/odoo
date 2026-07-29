from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

@tagged('post_install', '-at_install')
class TestLhiApprovalMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestLhiApprovalMatrix, cls).setUpClass()

        cls.company = cls.env.company
        
        # Setup groups
        cls.group_employee = cls.env.ref('lhi_security.group_lhi_employee')
        cls.group_manager = cls.env.ref('lhi_security.group_lhi_manager')
        cls.group_officer = cls.env.ref('lhi_security.group_lhi_procurement_officer')
        cls.group_finance = cls.env.ref('lhi_security.group_lhi_finance_reviewer')

        # Setup test users
        cls.user_creator = cls.env['res.users'].create({
            'name': 'Document Creator',
            'login': 'doc_creator',
            'email': 'creator@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id])],
        })

        cls.user_reviewer = cls.env['res.users'].create({
            'name': 'Document Reviewer',
            'login': 'doc_reviewer',
            'email': 'reviewer@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_officer.id])],
        })

        cls.user_approver = cls.env['res.users'].create({
            'name': 'Document Approver',
            'login': 'doc_approver',
            'email': 'approver@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_manager.id])],
        })

        cls.user_escalate = cls.env['res.users'].create({
            'name': 'Escalation Target',
            'login': 'doc_escalate',
            'email': 'escalate@lhinigeria.org',
            'group_ids': [(6, 0, [cls.group_employee.id, cls.group_manager.id])],
        })

        # Setup base master records to match matrix
        cls.office = cls.env['lhi.office'].create({
            'name': 'Zonal Office',
            'code': 'ZO-OFF',
            'company_id': cls.company.id,
        })

        cls.project = cls.env['lhi.project'].create({
            'name': 'WASH Project',
            'code': 'PRJ-WSH',
            'office_id': cls.office.id,
            'company_id': cls.company.id,
        })

        # Define an Approval Matrix config
        cls.matrix = cls.env['lhi.approval.matrix'].create({
            'name': 'WASH Project Matrix',
            'document_type': 'purchase',
            'min_amount': 5000.0,
            'max_amount': 50000.0,
            'company_id': cls.company.id,
            'project_ids': [(6, 0, [cls.project.id])],
            'line_ids': [
                (0, 0, {
                    'name': 'Technical Review',
                    'sequence': 1,
                    'approver_group_id': cls.group_officer.id,
                    'approval_type': 'any',
                    'timeout_days': 1,
                    'escalation_user_id': cls.user_escalate.id,
                }),
                (0, 0, {
                    'name': 'Financial Signoff',
                    'sequence': 2,
                    'approver_group_id': cls.group_manager.id,
                    'approval_type': 'any',
                    'timeout_days': 3,
                }),
            ]
        })

    def test_01_sod_conflict_rules(self):
        """Verify that assigning conflicting roles raises ValidationError according to SoD rules."""
        # Create an active SoD rule: Officer vs Manager
        rule = self.env['lhi.sod.rule'].create({
            'name': 'Procurement vs Manager Rule',
            'group_1_id': self.group_officer.id,
            'group_2_id': self.group_manager.id,
            'is_active': True,
        })

        # Assign both groups to a user
        with self.assertRaises(ValidationError):
            self.user_creator.write({
                'group_ids': [(4, self.group_officer.id), (4, self.group_manager.id)]
            })
            self.env['lhi.sod.rule'].check_user_conflicts(self.user_creator)

    def test_02_approval_submission(self):
        """Test submitting request successfully matches matrix and instantiates lines."""
        # Create active request record
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })

        self.assertEqual(req.state, 'draft')
        
        # Submit
        req.action_submit()
        self.assertEqual(req.state, 'under_review')
        self.assertEqual(len(req.line_ids), 2)
        self.assertEqual(req.current_line_id.name, 'Technical Review')
        self.assertIn(self.user_reviewer.id, req.current_line_id.approver_ids.ids)

    def test_02b_prepare_snapshots_route_without_starting_approval(self):
        """Signature workflows may prepare recipients before active review."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })

        req.action_prepare()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(len(req.line_ids), 2)
        self.assertTrue(req.matrix_id)

        req.action_activate()
        self.assertEqual(req.state, 'under_review')

    def test_03_self_approval_prevention(self):
        """Verify creator cannot approve their own document step."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()
        
        # Add creator to the reviewer group temporarily to test self-approval check
        self.user_creator.write({
            'group_ids': [(4, self.group_officer.id)]
        })

        with self.assertRaises(UserError):
            req.with_user(self.user_creator).action_approve(notes='Self approval attempt')

    def test_04_approval_workflow_transitions(self):
        """Test complete workflow transition: Approve first step, delegation on second, full approval."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()

        # 1. Reviewer approves Technical Review
        req.with_user(self.user_reviewer).action_approve()
        self.assertEqual(req.current_line_id.name, 'Financial Signoff')
        self.assertEqual(req.state, 'under_review')

        # 2. Test Delegation: Approver delegates to Reviewer
        delegation = self.env['lhi.approval.delegation'].create({
            'delegator_id': self.user_approver.id,
            'delegatee_id': self.user_reviewer.id,
            'start_date': datetime.now() - timedelta(hours=1),
            'end_date': datetime.now() + timedelta(hours=1),
            'document_type': 'purchase',
            'active': True,
        })

        # Reviewer approves on behalf of Approver
        req.with_user(self.user_reviewer).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_05_return_for_correction(self):
        """Verify returning for correction resets approval steps and requests."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()

        # Technical Reviewer returns for correction
        req.with_user(self.user_reviewer).action_return_for_correction(notes='Missing tech documents')
        self.assertEqual(req.state, 'returned')
        self.assertEqual(req.line_ids[0].state, 'pending')

    def test_05b_only_current_approver_can_reject_or_return(self):
        """Decision RPC methods enforce the current-stage approver boundary."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()

        with self.assertRaises(UserError):
            req.with_user(self.user_approver).action_reject(
                notes='Not the current-stage approver'
            )
        with self.assertRaises(UserError):
            req.with_user(self.user_approver).action_return_for_correction(
                notes='Not the current-stage approver'
            )
        self.assertEqual(req.state, 'under_review')
        self.assertEqual(req.current_line_id.name, 'Technical Review')

    def test_05c_decision_reasons_are_mandatory(self):
        """Rejections and returns require an auditable reason."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()

        with self.assertRaises(ValidationError):
            req.with_user(self.user_reviewer).action_reject(notes=' ')
        with self.assertRaises(ValidationError):
            req.with_user(self.user_reviewer).action_return_for_correction()
        self.assertEqual(req.state, 'under_review')

    def test_06_timeout_escalation(self):
        """Verify that step timeout escalates step to the escalation user."""
        req = self.env['lhi.approval.request'].create({
            'res_model': 'lhi.project',
            'res_id': self.project.id,
            'document_type': 'purchase',
            'amount': 10000.0,
            'currency_id': self.company.currency_id.id,
            'creator_id': self.user_creator.id,
            'project_id': self.project.id,
            'company_id': self.company.id,
        })
        req.action_submit()

        # Simulate timeout: rewrite request write_date to 2 days ago (timeout is 1 day)
        past_date = fields.Datetime.now() - timedelta(days=2)
        self.env.flush_all()
        self.cr.execute("UPDATE lhi_approval_request SET write_date = %s WHERE id = %s", (past_date, req.id))
        self.env.invalidate_all()

        # Run escalation runner
        self.env['lhi.approval.request'].check_and_escalate_timeouts()
        
        # Verify step 1 has been escalated
        self.assertIn(self.user_escalate.id, req.current_line_id.approver_ids.ids)

    def test_07_accounting_feature_flag(self):
        """Verify feature gate blocks operations when disabled."""
        # Find or create flag
        flag = self.env['lhi.feature.flag'].search([('name', '=', 'lhi_accounting_enabled')], limit=1)
        if not flag:
            flag = self.env['lhi.feature.flag'].create({
                'name': 'lhi_accounting_enabled',
                'description': 'LHI Accounting feature gate',
                'is_enabled': False,
            })
        else:
            flag.write({'is_enabled': False})

        # Calling check_accounting_enabled should raise UserError
        with self.assertRaises(UserError):
            self.env['lhi.feature.flag'].check_accounting_enabled()

        # Try to post or manipulate account.move if the module is installed
        if 'account.move' in self.env:
            with self.assertRaises(UserError):
                self.env['account.move'].create({
                    'move_type': 'entry',
                    'ref': 'Test Block',
                })
