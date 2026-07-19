from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user


class TestProgrammeLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["lhi.project"].create({"name": "Test Project", "code": "TP-001"})
        donor = cls.env["lhi.donor"].create({"name": "Test Donor", "code": "TD-001"})
        funding = cls.env["lhi.funding.source"].create({"name": "Test Funding", "code": "TF-001", "donor_id": donor.id})
        cls.award = cls.env["lhi.award"].create({"name": "Test Award", "code": "TA-001", "funding_source_id": funding.id, "currency_id": cls.env.company.currency_id.id})
        cls.project.award_id = cls.award
        cls.workplan = cls.env["lhi.workplan"].create({"name": "Test Workplan", "project_id": cls.project.id, "plan_type": "annual", "start_date": "2026-01-01", "end_date": "2026-12-31"})
        cls.activity = cls.env["lhi.workplan.activity"].create({"name": "Test Activity", "workplan_id": cls.workplan.id, "element_type": "activity"})
        cls.budget = cls.env["lhi.project.budget"].create({"name": "FY26", "project_id": cls.project.id, "grant_id": cls.award.id, "total_approved_budget": 1000, "fiscal_period": "2026"})
        cls.line = cls.env["lhi.project.budget.line"].create({"budget_id": cls.budget.id, "code": "BL-1", "name": "Activities", "approved_amount": 1000, "activity_id": cls.activity.id})

    def test_project_request_requires_approved_memo(self):
        request = self.env["lhi.execution.request"].create({"request_type": "travel", "work_context": "project_linked", "project_id": self.project.id, "grant_id": self.award.id, "activity_id": self.activity.id, "budget_line_id": self.line.id, "requested_amount": 100})
        with self.assertRaises(ValidationError):
            request.action_submit()

    def test_standalone_request_does_not_require_project(self):
        request = self.env["lhi.execution.request"].create({"request_type": "media", "work_context": "standalone_departmental", "requested_amount": 10})
        request.action_submit()
        self.assertEqual(request.state, "submitted")

    def test_approved_memo_unlocks_matching_project_request(self):
        memo = self.env["lhi.activity.memo"].create({
            "project_id": self.project.id,
            "grant_id": self.award.id,
            "activity_id": self.activity.id,
            "budget_line_id": self.line.id,
            "requested_amount": 100,
            "approved_amount": 80,
            "purpose": "Test delivery",
            "justification": "Required test execution",
            "implementation_start_date": "2026-03-01",
            "implementation_end_date": "2026-03-02",
        })
        memo.action_submit()
        memo.action_start_line_manager_review()
        memo.action_line_manager_approve()
        memo.action_project_manager_approve()
        memo.action_finance_approve()
        memo.action_approve()
        request = self.env["lhi.execution.request"].create({
            "request_type": "travel",
            "work_context": "project_linked",
            "project_id": self.project.id,
            "grant_id": self.award.id,
            "activity_id": self.activity.id,
            "memo_id": memo.id,
            "budget_line_id": self.line.id,
            "requested_amount": 75,
        })
        request.action_submit()
        self.assertEqual(request.state, "submitted")

    def test_paid_state_requires_enterprise_reference(self):
        request = self.env["lhi.execution.request"].create({"request_type": "payment", "requested_amount": 10, "state": "processing"})
        with self.assertRaises(ValidationError):
            request.action_mark_paid()

    def test_programme_user_can_create_but_ordinary_user_cannot_read_requests(self):
        programme_user = new_test_user(self.env, login="programme_lifecycle_user", groups="lhi_programme_management.group_lhi_programmes_user")
        ordinary_user = new_test_user(self.env, login="programme_lifecycle_ordinary", groups="base.group_user")
        request = self.env["lhi.execution.request"].with_user(programme_user).create({"request_type": "meal", "requested_amount": 5})
        self.assertTrue(request.exists())
        with self.assertRaises(AccessError):
            request.with_user(ordinary_user).check_access("read")

    def test_programme_user_cannot_invoke_manager_approval_over_rpc(self):
        programme_user = new_test_user(self.env, login="programme_no_approval", groups="lhi_programme_management.group_lhi_programmes_user")
        request = self.env["lhi.execution.request"].with_user(programme_user).create({
            "request_type": "media",
            "requested_amount": 5,
        })
        request.action_submit()
        with self.assertRaises(AccessError):
            request.action_manager_approve()
