from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def _currency(env, code):
    return (
        env["res.currency"]
        .with_context(active_test=False)
        .search([("name", "=", code)], limit=1)
    )


class LhiAward(models.Model):
    _inherit = "lhi.award"

    # Most LHI donor-funded awards are USD.
    # Existing records are not altered.
    currency_id = fields.Many2one(
        "res.currency",
        string="Award Currency",
        required=True,
        default=lambda self: (
            _currency(self.env, "USD")
            or self.env.company.currency_id
        ),
    )

    original_start_date = fields.Date(
        string="Original Start Date",
        tracking=True,
        copy=False,
    )

    original_end_date = fields.Date(
        string="Original End Date",
        tracking=True,
        copy=False,
    )

    amendment_ids = fields.One2many(
        "lhi.award.amendment",
        "award_id",
        string="Award Amendments",
    )

    original_award_amount = fields.Monetary(
        string="Original Signed Award",
        currency_field="currency_id",
        compute="_compute_award_values",
    )

    approved_amendment_amount = fields.Monetary(
        string="Approved Amendments",
        currency_field="currency_id",
        compute="_compute_award_values",
    )

    current_award_amount = fields.Monetary(
        string="Current Approved Award Value",
        currency_field="currency_id",
        compute="_compute_award_values",
    )

    @api.depends(
        "amount",
        "amendment_ids.state",
        "amendment_ids.amount_change",
    )
    def _compute_award_values(self):
        for award in self:
            approved = award.amendment_ids.filtered(
                lambda amendment:
                    amendment.state == "approved"
            )

            amendment_total = sum(
                approved.mapped("amount_change")
            )

            award.original_award_amount = (
                award.amount or 0.0
            )

            award.approved_amendment_amount = (
                amendment_total
            )

            award.current_award_amount = (
                (award.amount or 0.0)
                + amendment_total
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("start_date")
                and not vals.get("original_start_date")
            ):
                vals["original_start_date"] = (
                    vals["start_date"]
                )

            if (
                vals.get("end_date")
                and not vals.get("original_end_date")
            ):
                vals["original_end_date"] = (
                    vals["end_date"]
                )

        return super().create(vals_list)

    def action_open_award_amendments(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Award Amendments"),
            "res_model": "lhi.award.amendment",
            "view_mode": "list,form",
            "domain": [
                ("award_id", "=", self.id),
            ],
            "context": {
                "default_award_id": self.id,
            },
        }


class LhiAwardAmendment(models.Model):
    _name = "lhi.award.amendment"
    _description = "LHI Award Amendment"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]
    _order = "effective_date desc, id desc"

    name = fields.Char(
        string="Amendment Reference",
        default="New",
        required=True,
        copy=False,
        tracking=True,
    )

    award_id = fields.Many2one(
        "lhi.award",
        string="Award",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    amendment_type = fields.Selection(
        [
            (
                "additional_funding",
                "Additional Funding",
            ),
            (
                "budget_reduction",
                "Budget Reduction",
            ),
            (
                "no_cost_extension",
                "No-Cost Extension",
            ),
            (
                "cost_extension",
                "Cost Extension",
            ),
            (
                "scope_amendment",
                "Scope Amendment",
            ),
            (
                "budget_realignment",
                "Budget Realignment",
            ),
            (
                "other",
                "Other",
            ),
        ],
        required=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="award_id.currency_id",
        store=True,
        readonly=True,
    )

    amount_change = fields.Monetary(
        string="Funding Change",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
        help=(
            "Positive for additional funding, "
            "negative for a reduction, and zero "
            "for a no-cost extension."
        ),
    )

    previous_amount = fields.Monetary(
        string="Previous Award Value",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    revised_amount = fields.Monetary(
        string="Revised Award Value",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    previous_end_date = fields.Date(
        string="Previous End Date",
        readonly=True,
        copy=False,
    )

    revised_end_date = fields.Date(
        string="Revised End Date",
        tracking=True,
    )

    effective_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    donor_approval_date = fields.Date(
        string="Donor Approval Date",
        tracking=True,
    )

    reason = fields.Char(
        required=True,
        tracking=True,
    )

    description = fields.Text(
        string="Amendment Details",
        tracking=True,
    )

    approval_document_id = fields.Many2one(
        "ir.attachment",
        string="Approved Amendment Document",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        copy=False,
    )

    approved_at = fields.Datetime(
        string="Approved At",
        readonly=True,
        copy=False,
    )

    company_id = fields.Many2one(
        "res.company",
        related="award_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"]
                    .next_by_code(
                        "lhi.award.amendment"
                    )
                    or "New"
                )

        return super().create(vals_list)

    @api.constrains(
        "amendment_type",
        "amount_change",
        "revised_end_date",
    )
    def _check_amendment(self):
        for amendment in self:
            if (
                amendment.amendment_type
                == "additional_funding"
                and amendment.amount_change <= 0
            ):
                raise ValidationError(
                    _(
                        "Additional Funding must have "
                        "a positive funding change."
                    )
                )

            if (
                amendment.amendment_type
                == "budget_reduction"
                and amendment.amount_change >= 0
            ):
                raise ValidationError(
                    _(
                        "Budget Reduction must have "
                        "a negative funding change."
                    )
                )

            if (
                amendment.amendment_type
                == "no_cost_extension"
                and amendment.amount_change != 0
            ):
                raise ValidationError(
                    _(
                        "A No-Cost Extension cannot "
                        "change the award value."
                    )
                )

            if (
                amendment.amendment_type
                in (
                    "no_cost_extension",
                    "cost_extension",
                )
                and not amendment.revised_end_date
            ):
                raise ValidationError(
                    _(
                        "An extension requires a "
                        "revised end date."
                    )
                )

    def _check_finance_permission(self):
        allowed = (
            self.env.is_superuser()
            or self.env.user.has_group(
                "lhi_programme_management."
                "group_lhi_programmes_finance_manager"
            )
            or self.env.user.has_group(
                "base.group_system"
            )
        )

        if not allowed:
            raise AccessError(
                _(
                    "Only Finance Managers or ERP "
                    "Administrators can approve "
                    "award amendments."
                )
            )

    def action_submit(self):
        for amendment in self:
            if amendment.state != "draft":
                raise ValidationError(
                    _(
                        "Only draft amendments can "
                        "be submitted."
                    )
                )

            amendment.state = "submitted"

    def action_approve(self):
        self._check_finance_permission()

        for amendment in self:
            if amendment.state != "submitted":
                raise ValidationError(
                    _(
                        "Only submitted amendments "
                        "can be approved."
                    )
                )

            award = amendment.award_id

            previous_amount = (
                award.current_award_amount
            )

            revised_amount = (
                previous_amount
                + amendment.amount_change
            )

            if revised_amount < 0:
                raise ValidationError(
                    _(
                        "The amendment would make "
                        "the award value negative."
                    )
                )

            vals = {
                "previous_amount":
                    previous_amount,
                "revised_amount":
                    revised_amount,
                "previous_end_date":
                    award.end_date,
                "approved_by_id":
                    self.env.user.id,
                "approved_at":
                    fields.Datetime.now(),
                "state":
                    "approved",
            }

            amendment.write(vals)

            if amendment.revised_end_date:
                award.write(
                    {
                        "end_date":
                            amendment.revised_end_date
                    }
                )

    def action_reject(self):
        self._check_finance_permission()

        for amendment in self:
            if amendment.state != "submitted":
                raise ValidationError(
                    _(
                        "Only submitted amendments "
                        "can be rejected."
                    )
                )

            amendment.state = "rejected"

    def write(self, vals):
        protected_fields = {
            "award_id",
            "amendment_type",
            "amount_change",
            "revised_end_date",
            "effective_date",
            "donor_approval_date",
        }

        if protected_fields.intersection(vals):
            for amendment in self:
                if amendment.state == "approved":
                    raise ValidationError(
                        _(
                            "An approved amendment "
                            "cannot be modified."
                        )
                    )

        return super().write(vals)

    def unlink(self):
        for amendment in self:
            if amendment.state == "approved":
                raise ValidationError(
                    _(
                        "Approved amendments cannot "
                        "be deleted."
                    )
                )

        return super().unlink()


class LhiProjectFxRate(models.Model):
    _name = "lhi.project.fx.rate"
    _description = "LHI Project Exchange Rate"
    _inherit = ["mail.thread"]
    _order = "effective_at desc, id desc"

    scope = fields.Selection(
        [
            ("global", "Organization Rate"),
            ("project", "Project / Donor Rate"),
        ],
        required=True,
        default="global",
        tracking=True,
    )

    project_id = fields.Many2one(
        "lhi.project",
        string="Project",
        ondelete="cascade",
        index=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Foreign Currency",
        required=True,
        default=lambda self: (
            _currency(self.env, "USD")
            or self.env.company.currency_id
        ),
        tracking=True,
    )

    ngn_currency_id = fields.Many2one(
        "res.currency",
        string="Target Currency",
        required=True,
        default=lambda self: (
            _currency(self.env, "NGN")
            or self.env.company.currency_id
        ),
        tracking=True,
    )

    rate = fields.Float(
        string="NGN per 1 Foreign Currency",
        required=True,
        digits=(16, 6),
        tracking=True,
    )

    effective_at = fields.Datetime(
        string="Effective From",
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
    )

    source = fields.Selection(
        [
            ("manual", "Manual Finance Rate"),
            ("donor", "Donor Prescribed Rate"),
            ("automatic", "Automatic Provider"),
        ],
        required=True,
        default="manual",
        tracking=True,
    )

    provider_name = fields.Char(
        string="Provider / Source Name",
        tracking=True,
    )

    source_reference = fields.Char(
        string="Source Reference",
        tracking=True,
    )

    reason = fields.Text(
        string="Reason / Notes",
        tracking=True,
    )

    entered_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.onchange("scope")
    def _onchange_scope(self):
        if self.scope == "global":
            self.project_id = False

    @api.constrains(
        "scope",
        "project_id",
        "currency_id",
        "ngn_currency_id",
        "rate",
    )
    def _check_fx(self):
        for rate in self:
            if rate.rate <= 0:
                raise ValidationError(
                    _(
                        "Exchange rate must be "
                        "greater than zero."
                    )
                )

            if (
                rate.ngn_currency_id.name
                != "NGN"
            ):
                raise ValidationError(
                    _(
                        "The target currency must "
                        "be NGN."
                    )
                )

            if (
                rate.currency_id
                == rate.ngn_currency_id
            ):
                raise ValidationError(
                    _(
                        "Foreign currency and NGN "
                        "cannot be the same."
                    )
                )

            if (
                rate.scope == "project"
                and not rate.project_id
            ):
                raise ValidationError(
                    _(
                        "A Project / Donor rate "
                        "must specify a project."
                    )
                )

            if (
                rate.scope == "global"
                and rate.project_id
            ):
                raise ValidationError(
                    _(
                        "An Organization Rate "
                        "cannot be tied to a project."
                    )
                )

            if (
                rate.project_id
                and rate.project_id.company_id
                != rate.company_id
            ):
                raise ValidationError(
                    _(
                        "The FX rate company must "
                        "match the project company."
                    )
                )


class LhiProject(models.Model):
    _inherit = "lhi.project"

    project_currency_id = fields.Many2one(
        "res.currency",
        string="Project / Donor Currency",
        compute="_compute_project_award_finance",
    )

    original_award_amount = fields.Monetary(
        string="Original Signed Award",
        currency_field="project_currency_id",
        compute="_compute_project_award_finance",
    )

    current_award_amount = fields.Monetary(
        string="Current Approved Award",
        currency_field="project_currency_id",
        compute="_compute_project_award_finance",
    )

    ngn_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_project_award_finance",
    )

    current_fx_rate = fields.Float(
        string="Current FX Rate to NGN",
        compute="_compute_project_fx",
        digits=(16, 6),
    )

    current_fx_date = fields.Datetime(
        string="FX Effective From",
        compute="_compute_project_fx",
    )

    current_fx_source = fields.Char(
        string="FX Rate Source",
        compute="_compute_project_fx",
    )

    current_ngn_equivalent = fields.Monetary(
        string="Current NGN Equivalent",
        currency_field="ngn_currency_id",
        compute="_compute_project_fx",
    )

    @api.depends(
        "award_id",
        "award_id.currency_id",
        "award_id.amount",
        "award_id.current_award_amount",
    )
    def _compute_project_award_finance(self):
        ngn = _currency(
            self.env,
            "NGN",
        )

        for project in self:
            if project.award_id:
                project.project_currency_id = (
                    project.award_id.currency_id
                )

                project.original_award_amount = (
                    project.award_id.amount
                    or 0.0
                )

                project.current_award_amount = (
                    project.award_id
                    .current_award_amount
                    or 0.0
                )
            else:
                project.project_currency_id = (
                    project.company_id.currency_id
                )

                project.original_award_amount = (
                    0.0
                )

                project.current_award_amount = (
                    0.0
                )

            project.ngn_currency_id = (
                ngn
                or project.company_id.currency_id
            )

    def _latest_fx_rate(self):
        self.ensure_one()

        currency = self.project_currency_id
        ngn = self.ngn_currency_id

        if (
            not currency
            or not ngn
            or currency == ngn
        ):
            return False

        now = fields.Datetime.now()

        Rate = self.env[
            "lhi.project.fx.rate"
        ].sudo()

        project_rate = Rate.search(
            [
                ("scope", "=", "project"),
                ("project_id", "=", self.id),
                ("currency_id", "=", currency.id),
                ("ngn_currency_id", "=", ngn.id),
                ("company_id", "=", self.company_id.id),
                ("effective_at", "<=", now),
            ],
            order="effective_at desc, id desc",
            limit=1,
        )

        if project_rate:
            return project_rate

        return Rate.search(
            [
                ("scope", "=", "global"),
                ("currency_id", "=", currency.id),
                ("ngn_currency_id", "=", ngn.id),
                ("company_id", "=", self.company_id.id),
                ("effective_at", "<=", now),
            ],
            order="effective_at desc, id desc",
            limit=1,
        )

    @api.depends(
        "award_id",
        "award_id.currency_id",
        "award_id.current_award_amount",
    )
    def _compute_project_fx(self):
        now = fields.Datetime.now()

        for project in self:
            project.current_fx_rate = 0.0
            project.current_fx_date = False
            project.current_fx_source = False
            project.current_ngn_equivalent = 0.0

            currency = project.project_currency_id
            ngn = project.ngn_currency_id

            if not currency or not ngn:
                continue

            if currency == ngn:
                project.current_fx_rate = 1.0
                project.current_fx_date = now
                project.current_fx_source = (
                    _("Project Currency")
                )
                project.current_ngn_equivalent = (
                    project.current_award_amount
                )
                continue

            rate = project._latest_fx_rate()

            if not rate:
                continue

            source = dict(
                rate._fields[
                    "source"
                ].selection
            ).get(
                rate.source,
                rate.source,
            )

            if rate.provider_name:
                source = "%s - %s" % (
                    source,
                    rate.provider_name,
                )

            if rate.scope == "project":
                source = "%s (%s)" % (
                    source,
                    _("Project Specific"),
                )

            project.current_fx_rate = (
                rate.rate
            )

            project.current_fx_date = (
                rate.effective_at
            )

            project.current_fx_source = (
                source
            )

            project.current_ngn_equivalent = (
                project.current_award_amount
                * rate.rate
            )

    def action_open_fx_history(self):
        self.ensure_one()

        currency = self.project_currency_id

        domain = [
            ("company_id", "=", self.company_id.id),
        ]

        if currency:
            domain.append(
                (
                    "currency_id",
                    "=",
                    currency.id,
                )
            )

        domain += [
            "|",
            ("scope", "=", "global"),
            ("project_id", "=", self.id),
        ]

        return {
            "type": "ir.actions.act_window",
            "name": _("Exchange Rate History"),
            "res_model": "lhi.project.fx.rate",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_scope": "project",
                "default_project_id": self.id,
                "default_currency_id":
                    currency.id
                    if currency
                    else False,
                "default_ngn_currency_id":
                    self.ngn_currency_id.id
                    if self.ngn_currency_id
                    else False,
                "default_company_id":
                    self.company_id.id,
            },
        }

    def lhi_project_dashboard_data(
        self,
        year=False,
        quarter="all",
    ):
        self.ensure_one()

        result = super().lhi_project_dashboard_data(
            year=year,
            quarter=quarter,
        )

        award = self.award_id
        currency = self.project_currency_id
        ngn = self.ngn_currency_id

        is_foreign = bool(
            award
            and currency
            and ngn
            and currency != ngn
        )

        result["project_fx"] = {
            "has_award": bool(award),
            "currency_code": (
                currency.name
                if currency
                else "NGN"
            ),
            "original_award": (
                self.original_award_amount
                or 0.0
            ),
            "current_award": (
                self.current_award_amount
                or 0.0
            ),
            "ngn_code": (
                ngn.name
                if ngn
                else "NGN"
            ),
            "ngn_equivalent": (
                self.current_ngn_equivalent
                or 0.0
            ),
            "rate": (
                self.current_fx_rate
                or 0.0
            ),
            "rate_date": (
                fields.Datetime.to_string(
                    self.current_fx_date
                )
                if self.current_fx_date
                else False
            ),
            "rate_source": (
                self.current_fx_source
                or False
            ),
            "is_foreign_currency":
                is_foreign,
        }

        # The existing budget-line calculations remain
        # untouched for committed/paid/available.
        #
        # Only the headline Approved Budget uses the
        # current formally approved donor award value.
        if award:
            for section in result.get(
                "sections", []
            ):
                for metric in section.get(
                    "metrics", []
                ):
                    if (
                        metric.get("code")
                        != "budget_approved"
                    ):
                        continue

                    metric["value"] = (
                        self.current_award_amount
                    )

                    metric[
                        "project_currency_value"
                    ] = (
                        self.current_award_amount
                    )

                    metric[
                        "project_currency_code"
                    ] = (
                        currency.name
                        if currency
                        else "NGN"
                    )

                    metric[
                        "ngn_currency_code"
                    ] = (
                        ngn.name
                        if ngn
                        else "NGN"
                    )

                    metric["ngn_value"] = (
                        self.current_ngn_equivalent
                        if (
                            not is_foreign
                            or self.current_fx_rate
                        )
                        else None
                    )

                    metric["dual_currency"] = (
                        is_foreign
                    )

        return result
