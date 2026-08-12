from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def _require_group(recordset, group_xmlid, message):
    if not recordset.env.user.has_group(group_xmlid):
        raise AccessError(message)


class LhiProjectBudget(models.Model):
    _name = "lhi.project.budget"
    _description = "LHI Project Budget"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one("lhi.project", required=True, ondelete="restrict", tracking=True)
    grant_id = fields.Many2one("lhi.award", required=True, ondelete="restrict", tracking=True)
    donor_id = fields.Many2one("lhi.donor", tracking=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    total_approved_budget = fields.Monetary(required=True, currency_field="currency_id", tracking=True)
    fiscal_period = fields.Char(required=True)
    state = fields.Selection([("draft", "Draft"), ("approved", "Approved"), ("locked", "Locked"), ("closed", "Closed")], default="draft", required=True, tracking=True)
    budget_line_ids = fields.One2many("lhi.project.budget.line", "budget_id")
    notes = fields.Text()
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    _project_period_unique = models.Constraint("unique(project_id, fiscal_period, company_id)", "A project can have only one budget per fiscal period and company.")

    def action_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("Only a Programs and Grants Manager can approve a budget."))
        for record in self:
            if record.state != "draft":
                raise ValidationError(_("Only draft budgets can be approved."))
            if sum(record.budget_line_ids.mapped("approved_amount")) > record.total_approved_budget:
                raise ValidationError(_("Budget lines exceed the approved project budget."))
            record.state = "approved"


class LhiProjectBudgetLine(models.Model):
    _name = "lhi.project.budget.line"
    _description = "LHI Project Budget Line"
    _inherit = ["mail.thread"]

    budget_id = fields.Many2one("lhi.project.budget", required=True, ondelete="cascade")
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    donor_budget_category = fields.Char()
    project_id = fields.Many2one(related="budget_id.project_id", store=True)
    grant_id = fields.Many2one(related="budget_id.grant_id", store=True)
    activity_id = fields.Many2one("lhi.workplan.activity")
    approved_amount = fields.Monetary(required=True, currency_field="currency_id")
    allocated_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    committed_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    approved_request_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    paid_reference_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    retired_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    available_amount = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    currency_id = fields.Many2one(related="budget_id.currency_id", store=True)
    allow_overspend = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    allocation_ids = fields.One2many("lhi.activity.budget.allocation", "budget_line_id")
    memo_ids = fields.One2many("lhi.activity.memo", "budget_line_id")
    request_ids = fields.One2many("lhi.execution.request", "budget_line_id")

    _code_budget_unique = models.Constraint("unique(budget_id, code)", "Budget line codes must be unique per budget.")

    @api.depends("approved_amount", "allocation_ids.allocated_amount", "memo_ids.approved_amount", "memo_ids.state", "request_ids.approved_amount", "request_ids.paid_amount", "request_ids.retired_amount", "request_ids.state")
    def _compute_amounts(self):
        for line in self:
            line.allocated_amount = sum(line.allocation_ids.filtered(lambda r: r.state in ("approved", "locked", "closed")).mapped("allocated_amount"))
            line.committed_amount = sum(line.memo_ids.filtered(lambda r: r.state in ("approved", "closed")).mapped("approved_amount"))
            line.approved_request_amount = sum(line.request_ids.filtered(lambda r: r.state not in ("draft", "cancelled", "rejected")).mapped("approved_amount"))
            line.paid_reference_amount = sum(line.request_ids.filtered(lambda r: r.enterprise_payment_reference).mapped("paid_amount"))
            line.retired_amount = sum(line.request_ids.mapped("retired_amount"))
            line.available_amount = line.approved_amount - line.committed_amount

    @api.constrains("approved_amount")
    def _check_amount(self):
        if any(line.approved_amount < 0 for line in self):
            raise ValidationError(_("Approved budget amounts cannot be negative."))


class LhiActivityBudgetAllocation(models.Model):
    _name = "lhi.activity.budget.allocation"
    _description = "LHI Activity Budget Allocation"
    _inherit = ["mail.thread"]

    activity_id = fields.Many2one("lhi.workplan.activity", required=True, ondelete="restrict")
    project_id = fields.Many2one(related="activity_id.project_id", store=True)
    grant_id = fields.Many2one(related="budget_line_id.grant_id", store=True)
    budget_line_id = fields.Many2one("lhi.project.budget.line", required=True, ondelete="restrict")
    allocated_amount = fields.Monetary(required=True, currency_field="currency_id")
    committed_amount = fields.Monetary(related="budget_line_id.committed_amount")
    available_amount = fields.Monetary(compute="_compute_available", currency_field="currency_id")
    currency_id = fields.Many2one(related="budget_line_id.currency_id", store=True)
    state = fields.Selection([("draft", "Draft"), ("approved", "Approved"), ("locked", "Locked"), ("closed", "Closed")], default="draft", required=True, tracking=True)

    @api.depends("allocated_amount", "committed_amount")
    def _compute_available(self):
        for record in self:
            record.available_amount = record.allocated_amount - record.committed_amount


class LhiActivityMemo(models.Model):
    _name = "lhi.activity.memo"
    _description = "LHI Activity Memo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Memo Reference", required=True, default="New", copy=False, tracking=True)
    project_id = fields.Many2one("lhi.project", required=True, ondelete="restrict", tracking=True)
    grant_id = fields.Many2one("lhi.award", required=True, ondelete="restrict", tracking=True)
    donor_id = fields.Many2one("lhi.donor", tracking=True)
    activity_id = fields.Many2one("lhi.workplan.activity", required=True, ondelete="restrict", tracking=True)
    budget_line_id = fields.Many2one("lhi.project.budget.line", required=True, ondelete="restrict", tracking=True)
    requested_amount = fields.Monetary(required=True, currency_field="currency_id", tracking=True)
    approved_amount = fields.Monetary(currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    purpose = fields.Char(required=True)
    background = fields.Text()
    justification = fields.Text(required=True)
    expected_outputs = fields.Text()
    participants = fields.Text()
    department_ids = fields.Many2many("lhi.department", string="Departments Involved")
    implementation_start_date = fields.Date(required=True)
    implementation_end_date = fields.Date(required=True)
    location = fields.Char()
    risk_notes = fields.Text()
    logistics_required = fields.Text()
    document_item_ids = fields.Many2many("lhi.document.item", string="SharePoint Documents")
    finance_review_state = fields.Selection([("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", required=True, tracking=True)
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("line_manager", "Line Manager Review"), ("project_manager", "Project Manager Review"), ("finance", "Finance Budget Review"), ("director", "Director Review"), ("approved", "Approved for Execution"), ("returned", "Returned for Correction"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("closed", "Closed")], default="draft", required=True, tracking=True)
    request_ids = fields.One2many("lhi.execution.request", "memo_id")
    retirement_ids = fields.One2many("lhi.payment.retirement", "memo_id")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("lhi.activity.memo") or "New"
        return super().create(vals_list)

    @api.constrains("implementation_start_date", "implementation_end_date", "project_id", "activity_id", "budget_line_id")
    def _check_scope(self):
        for memo in self:
            if memo.implementation_start_date > memo.implementation_end_date:
                raise ValidationError(_("Implementation end date cannot precede the start date."))
            if memo.activity_id.project_id != memo.project_id or memo.budget_line_id.project_id != memo.project_id:
                raise ValidationError(_("Memo activity and budget line must belong to the selected project."))
            if memo.project_id.award_id and memo.grant_id != memo.project_id.award_id:
                raise ValidationError(_("The memo grant must match the project's award."))

    def _transition(self, source, target):
        for record in self:
            if record.state != source:
                raise ValidationError(_("Invalid memo transition from %(source)s to %(target)s.", source=record.state, target=target))
            record.state = target

    def action_submit(self): self._transition("draft", "submitted")
    def action_start_line_manager_review(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("A Programs and Grants Manager is required."))
        self._transition("submitted", "line_manager")

    def action_line_manager_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("A Programs and Grants Manager is required."))
        self._transition("line_manager", "project_manager")

    def action_project_manager_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("A Programs and Grants Manager is required."))
        self._transition("project_manager", "finance")

    def action_finance_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        self._transition("finance", "director")
        self.write({"finance_review_state": "approved"})

    def action_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_director", _("A Director Approver is required."))
        for memo in self:
            if memo.state != "director":
                raise ValidationError(_("Only memos at Director Review can be approved for execution."))
            if memo.finance_review_state != "approved":
                raise ValidationError(_("Finance budget review is required before execution approval."))
            if not memo.approved_amount or memo.approved_amount > memo.requested_amount:
                raise ValidationError(_("Enter an approved amount not exceeding the requested amount."))
            if not memo.budget_line_id.allow_overspend and memo.approved_amount > memo.budget_line_id.available_amount:
                raise ValidationError(_("The memo exceeds the available budget line balance."))
            memo.state = "approved"


class LhiExecutionRequest(models.Model):
    _name = "lhi.execution.request"
    _description = "LHI Project or Department Execution Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, default="New", copy=False)
    request_type = fields.Selection([("travel", "Travel / Advance"), ("payment", "General Payment"), ("procurement", "Procurement"), ("fleet", "Fleet"), ("inventory", "Inventory"), ("meal", "MEAL Support"), ("media", "Media Support")], required=True)
    work_context = fields.Selection([("project_linked", "Project-linked"), ("standalone_departmental", "Standalone departmental")], default="standalone_departmental", required=True, tracking=True)
    project_id = fields.Many2one("lhi.project")
    grant_id = fields.Many2one("lhi.award")
    activity_id = fields.Many2one("lhi.workplan.activity")
    memo_id = fields.Many2one("lhi.memo")
    budget_line_id = fields.Many2one("lhi.project.budget.line")
    requested_amount = fields.Monetary(required=True, currency_field="currency_id")
    approved_amount = fields.Monetary(currency_field="currency_id")
    paid_amount = fields.Monetary(currency_field="currency_id")
    retired_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    enterprise_payment_reference = fields.Char(copy=False, tracking=True)
    enterprise_payment_date = fields.Date(tracking=True)
    enterprise_record_url = fields.Char()
    accounting_notes = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("manager", "Line Manager Approved"), ("project_manager", "Project Manager Approved"), ("finance", "Finance Reviewed"), ("approved", "Approved for Payment"), ("processing", "Payment Processing"), ("paid", "Paid"), ("awaiting_retirement", "Awaiting Retirement"), ("retirement_review", "Retirement Under Review"), ("closed", "Closed"), ("returned", "Returned / Queried"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], default="draft", required=True, tracking=True)
    retirement_ids = fields.One2many("lhi.payment.retirement", "request_id")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New": vals["name"] = self.env["ir.sequence"].next_by_code("lhi.execution.request") or "New"
        return super().create(vals_list)

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise ValidationError(_("Only draft execution requests can be submitted."))
            if request.work_context == "project_linked":
                if not all((request.project_id, request.grant_id, request.activity_id, request.memo_id, request.budget_line_id)):
                    raise ValidationError(_("Project-linked requests require project, grant, activity, approved memo, and budget line."))
                if request.memo_id.state != "approved":
                    raise ValidationError(_("No approved activity memo, no project-funded execution request."))
                if request.activity_id.project_id != request.project_id or request.budget_line_id.project_id != request.project_id:
                    raise ValidationError(_("The request activity and budget line must belong to the selected project."))
                if request.memo_id.project_id != request.project_id or request.memo_id.activity_id != request.activity_id or request.memo_id.budget_line_id != request.budget_line_id:
                    raise ValidationError(_("The request must use the project, activity, and budget line approved by its memo."))
                if request.requested_amount > request.memo_id.approved_amount:
                    raise ValidationError(_("The request exceeds the memo-approved amount; approve a supplementary memo first."))
            request.state = "submitted"

    def _transition(self, source, target):
        for record in self:
            if record.state != source:
                raise ValidationError(_("Invalid request transition from %(source)s to %(target)s.", source=record.state, target=target))
            record.state = target

    def action_manager_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("A Programs and Grants Manager is required."))
        self._transition("submitted", "manager")

    def action_project_manager_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_manager", _("A Programs and Grants Manager is required."))
        self._transition("manager", "project_manager")

    def action_finance_review(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        self._transition("project_manager", "finance")

    def action_approve_payment(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_manager", _("A Finance Manager is required."))
        self._transition("finance", "approved")

    def action_start_payment(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        self._transition("approved", "processing")

    def action_mark_paid(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        for request in self:
            if request.state != "processing":
                raise ValidationError(_("Only requests in Payment Processing can be marked paid."))
            if not request.enterprise_payment_reference:
                raise ValidationError(_("An Enterprise Odoo payment reference is required before marking this request paid."))
            request.state = "awaiting_retirement"


class LhiPaymentRetirement(models.Model):
    _name = "lhi.payment.retirement"
    _description = "LHI Payment Retirement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Retirement Reference", required=True, default="New", copy=False)
    request_id = fields.Many2one("lhi.execution.request", required=True, ondelete="restrict")
    memo_id = fields.Many2one(related="request_id.memo_id", store=True)
    project_id = fields.Many2one(related="request_id.project_id", store=True)
    grant_id = fields.Many2one(related="request_id.grant_id", store=True)
    activity_id = fields.Many2one(related="request_id.activity_id", store=True)
    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    amount_advanced = fields.Monetary(related="request_id.paid_amount", currency_field="currency_id")
    amount_spent = fields.Monetary(currency_field="currency_id")
    amount_retired = fields.Monetary(currency_field="currency_id")
    amount_refunded = fields.Monetary(currency_field="currency_id")
    unsupported_amount = fields.Monetary(currency_field="currency_id")
    balance_due = fields.Monetary(compute="_compute_balance", currency_field="currency_id")
    currency_id = fields.Many2one(related="request_id.currency_id", store=True)
    document_item_ids = fields.Many2many("lhi.document.item", string="SharePoint Receipt Documents")
    activity_report = fields.Text()
    finance_review_notes = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("review", "Under Review"), ("approved", "Approved"), ("returned", "Returned"), ("closed", "Closed")], default="draft", required=True, tracking=True)
    company_id = fields.Many2one(related="request_id.company_id", store=True)

    @api.depends("amount_advanced", "amount_retired", "amount_refunded")
    def _compute_balance(self):
        for record in self: record.balance_due = record.amount_advanced - record.amount_retired - record.amount_refunded

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New": vals["name"] = self.env["ir.sequence"].next_by_code("lhi.payment.retirement") or "New"
        return super().create(vals_list)

    def action_submit(self):
        for retirement in self:
            if retirement.state != "draft":
                raise ValidationError(_("Only draft retirements can be submitted."))
            retirement.state = "submitted"

    def action_start_review(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        for retirement in self:
            if retirement.state != "submitted":
                raise ValidationError(_("Only submitted retirements can enter review."))
            retirement.state = "review"

    def action_approve(self):
        _require_group(self, "lhi_programme_management.group_lhi_programmes_finance_reviewer", _("A Finance Reviewer is required."))
        for retirement in self:
            if retirement.state != "review":
                raise ValidationError(_("Only retirements under review can be approved."))
            retirement.state = "approved"
            retirement.request_id.write({"retired_amount": retirement.amount_retired, "state": "closed" if retirement.balance_due <= 0 else "retirement_review"})
