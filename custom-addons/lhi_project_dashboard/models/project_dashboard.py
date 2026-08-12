import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


_logger = logging.getLogger(__name__)


AUTOMATIC_METRICS = [
    ("activities_total", "Total Activities"),
    ("activities_planned", "Planned Activities"),
    ("activities_in_progress", "Ongoing Activities"),
    ("activities_completed", "Completed Activities"),
    ("activities_delayed", "Delayed Activities"),
    ("activities_cancelled", "Cancelled Activities"),
    ("activities_completion_pct", "Activity Completion %"),
    ("indicators_total", "Total Indicators"),
    ("indicators_achieved", "Indicators Achieved"),
    ("indicators_progress_pct", "Indicator Progress %"),
    ("budget_approved", "Approved Budget"),
    ("budget_committed", "Committed Amount"),
    ("budget_paid", "Paid Amount"),
    ("budget_retired", "Retired Amount"),
    ("budget_available", "Available Budget"),
    ("budget_utilization_pct", "Budget Utilization %"),
]


class LhiProjectDashboardMetric(models.Model):
    _name = "lhi.project.dashboard.metric"
    _description = "Project Dashboard Metric"
    _order = "section, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)

    section = fields.Char(
        required=True,
        default="Project Metrics",
    )

    metric_type = fields.Selection(
        [
            ("automatic", "Automatic"),
            ("manual", "Manual"),
        ],
        required=True,
        default="manual",
    )

    automatic_code = fields.Selection(
        AUTOMATIC_METRICS,
        string="Automatic Calculation",
    )

    unit = fields.Selection(
        [
            ("number", "Number"),
            ("decimal", "Decimal"),
            ("percentage", "Percentage"),
            ("currency", "Currency"),
        ],
        required=True,
        default="number",
    )

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    default_for_projects = fields.Boolean(
        string="Add to Projects by Default",
        default=False,
    )

    description = fields.Text()

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Dashboard metric code must be unique.",
    )

    @api.constrains("metric_type", "automatic_code")
    def _check_metric_configuration(self):
        for metric in self:
            if (
                metric.metric_type == "automatic"
                and not metric.automatic_code
            ):
                raise ValidationError(
                    _(
                        "Automatic dashboard metrics require "
                        "an automatic calculation."
                    )
                )


class LhiProjectDashboardAssignment(models.Model):
    _name = "lhi.project.dashboard.assignment"
    _description = "Project Dashboard Metric Assignment"
    _order = "sequence, id"

    project_id = fields.Many2one(
        "lhi.project",
        required=True,
        ondelete="cascade",
        index=True,
    )

    metric_id = fields.Many2one(
        "lhi.project.dashboard.metric",
        required=True,
        ondelete="restrict",
    )

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    target_value = fields.Float(
        string="Target",
    )

    value_ids = fields.One2many(
        "lhi.project.dashboard.value",
        "assignment_id",
        string="Manual Values",
    )

    _project_metric_unique = models.Constraint(
        "UNIQUE(project_id, metric_id)",
        "A dashboard metric can only be assigned once to a project.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("metric_id")
                and "sequence" not in vals
            ):
                metric = self.env[
                    "lhi.project.dashboard.metric"
                ].browse(vals["metric_id"])

                vals["sequence"] = metric.sequence

        return super().create(vals_list)


class LhiProjectDashboardValue(models.Model):
    _name = "lhi.project.dashboard.value"
    _description = "Project Dashboard Manual Metric Value"
    _order = "year desc, period"

    assignment_id = fields.Many2one(
        "lhi.project.dashboard.assignment",
        required=True,
        ondelete="cascade",
        index=True,
    )

    project_id = fields.Many2one(
        related="assignment_id.project_id",
        store=True,
        index=True,
    )

    metric_id = fields.Many2one(
        related="assignment_id.metric_id",
        store=True,
        index=True,
    )

    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.context_today(
            self
        ).year,
    )

    period = fields.Selection(
        [
            ("q1", "Q1"),
            ("q2", "Q2"),
            ("q3", "Q3"),
            ("q4", "Q4"),
            ("annual", "Annual"),
        ],
        required=True,
        default="annual",
    )

    value = fields.Float(required=True)
    notes = fields.Text()

    updated_by_id = fields.Many2one(
        "res.users",
        readonly=True,
        default=lambda self: self.env.user,
    )

    updated_at = fields.Datetime(
        readonly=True,
        default=fields.Datetime.now,
    )

    _period_unique = models.Constraint(
        "UNIQUE(assignment_id, year, period)",
        "Only one value is allowed for each metric, year and period.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()

        for vals in vals_list:
            vals["updated_by_id"] = self.env.user.id
            vals["updated_at"] = now

        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        vals["updated_by_id"] = self.env.user.id
        vals["updated_at"] = fields.Datetime.now()
        return super().write(vals)


class LhiProject(models.Model):
    _inherit = "lhi.project"

    project_dashboard_widget = fields.Char(
        compute="_compute_project_dashboard_widget",
    )

    project_dashboard_assignment_ids = fields.One2many(
        "lhi.project.dashboard.assignment",
        "project_id",
        string="Dashboard Metrics",
    )

    def _compute_project_dashboard_widget(self):
        for project in self:
            project.project_dashboard_widget = "dashboard"

    def _dashboard_can_configure(self):
        return bool(
            self.env.user.has_group(
                "lhi_programme_management."
                "group_lhi_programmes_admin"
            )
            or self.env.user.has_group(
                "lhi_security.group_lhi_erp_admin"
            )
        )

    def _ensure_dashboard_assignments(self):
        self.ensure_one()

        Assignment = self.env[
            "lhi.project.dashboard.assignment"
        ].sudo()

        Metric = self.env[
            "lhi.project.dashboard.metric"
        ].sudo()

        metrics = Metric.search(
            [
                ("active", "=", True),
                ("default_for_projects", "=", True),
            ]
        )

        existing = Assignment.search(
            [
                ("project_id", "=", self.id),
            ]
        )

        existing_metric_ids = set(
            existing.mapped("metric_id").ids
        )

        values = []

        for metric in metrics:
            if metric.id in existing_metric_ids:
                continue

            values.append(
                {
                    "project_id": self.id,
                    "metric_id": metric.id,
                    "sequence": metric.sequence,
                    "active": True,
                }
            )

        if values:
            Assignment.create(values)

    def action_configure_project_dashboard(self):
        self.ensure_one()

        if not self._dashboard_can_configure():
            raise AccessError(
                _(
                    "Only Programs and Grants Administrators "
                    "can configure project dashboard metrics."
                )
            )

        self._ensure_dashboard_assignments()

        return {
            "type": "ir.actions.act_window",
            "name": _(
                "Dashboard Metrics - %s"
            ) % self.display_name,
            "res_model": "lhi.project.dashboard.assignment",
            "view_mode": "list,form",
            "domain": [
                ("project_id", "=", self.id),
            ],
            "context": {
                "default_project_id": self.id,
            },
            "target": "current",
        }

    def _dashboard_period_date(self, record):
        for field_name in (
            "planned_start",
            "actual_start",
            "planned_end",
            "actual_end",
            "create_date",
        ):
            if field_name not in record._fields:
                continue

            value = record[field_name]

            if not value:
                continue

            if isinstance(value, datetime):
                return value.date()

            if isinstance(value, date):
                return value

        return False

    def _dashboard_period_match(
        self,
        record,
        year,
        quarter,
    ):
        candidate = self._dashboard_period_date(record)

        if not candidate:
            return quarter == "all"

        if year and candidate.year != year:
            return False

        if quarter == "all":
            return True

        quarter_number = ((candidate.month - 1) // 3) + 1

        return quarter == f"q{quarter_number}"

    def _dashboard_activities(
        self,
        year,
        quarter,
    ):
        if "lhi.workplan.activity" not in self.env.registry.models:
            return self.env["lhi.project"]

        records = self.env[
            "lhi.workplan.activity"
        ].search(
            [
                ("project_id", "=", self.id),
            ]
        )

        return records.filtered(
            lambda record: self._dashboard_period_match(
                record,
                year,
                quarter,
            )
        )

    def _dashboard_indicators(self):
        if "lhi.indicator" not in self.env.registry.models:
            return False

        return self.env["lhi.indicator"].search(
            [
                ("project_id", "=", self.id),
            ]
        )

    def _dashboard_budget_lines(self):
        if (
            "lhi.project.budget.line"
            not in self.env.registry.models
        ):
            return False

        return self.env[
            "lhi.project.budget.line"
        ].search(
            [
                ("project_id", "=", self.id),
                (
                    "budget_id.state",
                    "in",
                    ("approved", "locked", "closed"),
                ),
            ]
        )

    def _automatic_dashboard_value(
        self,
        code,
        year,
        quarter,
    ):
        if code.startswith("activities_"):
            activities = self._dashboard_activities(
                year,
                quarter,
            )

            non_cancelled = activities.filtered(
                lambda item: item.state != "cancelled"
            )

            if code == "activities_total":
                return len(non_cancelled)

            if code == "activities_planned":
                return len(
                    activities.filtered(
                        lambda item: item.state
                        in ("draft", "approved")
                    )
                )

            if code == "activities_in_progress":
                return len(
                    activities.filtered(
                        lambda item: item.state
                        == "in_progress"
                    )
                )

            if code == "activities_completed":
                return len(
                    activities.filtered(
                        lambda item: item.state
                        == "completed"
                    )
                )

            if code == "activities_delayed":
                return len(
                    activities.filtered(
                        lambda item: item.state
                        == "delayed"
                    )
                )

            if code == "activities_cancelled":
                return len(
                    activities.filtered(
                        lambda item: item.state
                        == "cancelled"
                    )
                )

            if code == "activities_completion_pct":
                total = len(non_cancelled)

                if not total:
                    return 0.0

                completed = len(
                    non_cancelled.filtered(
                        lambda item: item.state
                        == "completed"
                    )
                )

                return round(
                    (completed / total) * 100,
                    1,
                )

        if code.startswith("indicators_"):
            indicators = self._dashboard_indicators()

            if indicators is False:
                return None

            if code == "indicators_total":
                return len(indicators)

            if code == "indicators_achieved":
                return len(
                    indicators.filtered(
                        lambda item: (
                            item.target > 0
                            and item.achieved_total
                            >= item.target
                        )
                    )
                )

            if code == "indicators_progress_pct":
                if not indicators:
                    return 0.0

                values = indicators.mapped(
                    "progress_percentage"
                )

                return round(
                    sum(values) / len(values),
                    1,
                )

        if code.startswith("budget_"):
            lines = self._dashboard_budget_lines()

            if lines is False:
                return None

            approved = sum(
                lines.mapped("approved_amount")
            )

            committed = sum(
                lines.mapped("committed_amount")
            )

            paid = sum(
                lines.mapped("paid_reference_amount")
            )

            retired = sum(
                lines.mapped("retired_amount")
            )

            available = sum(
                lines.mapped("available_amount")
            )

            if code == "budget_approved":
                return approved

            if code == "budget_committed":
                return committed

            if code == "budget_paid":
                return paid

            if code == "budget_retired":
                return retired

            if code == "budget_available":
                return available

            if code == "budget_utilization_pct":
                if not approved:
                    return 0.0

                return round(
                    (paid / approved) * 100,
                    1,
                )

        return None

    def _manual_dashboard_value(
        self,
        assignment,
        year,
        quarter,
    ):
        values = assignment.sudo().value_ids.filtered(
            lambda item: item.year == year
        )

        if quarter != "all":
            value = values.filtered(
                lambda item: item.period == quarter
            )[:1]

            return value.value if value else None

        annual = values.filtered(
            lambda item: item.period == "annual"
        )[:1]

        if annual:
            return annual.value

        quarterly = values.filtered(
            lambda item: item.period
            in ("q1", "q2", "q3", "q4")
        )

        if quarterly:
            return sum(
                quarterly.mapped("value")
            )

        return None

    def _dashboard_years(self):
        self.ensure_one()

        current_year = fields.Date.context_today(
            self
        ).year

        years = {current_year}

        if self.start_date:
            years.add(self.start_date.year)

        if self.end_date:
            years.add(self.end_date.year)

        if self.start_date and self.end_date:
            start = self.start_date.year
            end = self.end_date.year

            if end >= start and (end - start) <= 15:
                years.update(
                    range(start, end + 1)
                )

        manual_years = (
            self.env[
                "lhi.project.dashboard.value"
            ]
            .sudo()
            .search(
                [
                    ("project_id", "=", self.id),
                ]
            )
            .mapped("year")
        )

        years.update(
            year
            for year in manual_years
            if year
        )

        return sorted(
            years,
            reverse=True,
        )

    def _dashboard_metadata(self):
        self.ensure_one()

        result = []

        candidates = (
            ("programme_id", _("Programme")),
            ("donor_id", _("Donor")),
            ("award_id", _("Award")),
            ("project_manager_id", _("Project Manager")),
        )

        for field_name, label in candidates:
            if field_name not in self._fields:
                continue

            value = self[field_name]

            if not value:
                continue

            result.append(
                {
                    "label": label,
                    "value": value.display_name,
                }
            )

        return result

    def lhi_project_dashboard_data(
        self,
        year=False,
        quarter="all",
    ):
        self.ensure_one()

        self.check_access("read")

        self._ensure_dashboard_assignments()

        quarter = (
            quarter
            if quarter in (
                "all",
                "q1",
                "q2",
                "q3",
                "q4",
            )
            else "all"
        )

        years = self._dashboard_years()

        try:
            year = int(year) if year else False
        except (TypeError, ValueError):
            year = False

        if not year:
            year = (
                years[0]
                if years
                else fields.Date.context_today(
                    self
                ).year
            )

        assignments = (
            self.env[
                "lhi.project.dashboard.assignment"
            ]
            .sudo()
            .search(
                [
                    ("project_id", "=", self.id),
                    ("active", "=", True),
                    ("metric_id.active", "=", True),
                ],
                order="sequence,id",
            )
        )

        section_map = {}

        for assignment in assignments:
            metric = assignment.metric_id

            try:
                if metric.metric_type == "automatic":
                    value = self._automatic_dashboard_value(
                        metric.automatic_code,
                        year,
                        quarter,
                    )
                else:
                    value = self._manual_dashboard_value(
                        assignment,
                        year,
                        quarter,
                    )
            except AccessError:
                # Preserve downstream model ACLs. A project dashboard
                # must not become a privilege-escalation path.
                continue
            except Exception:
                _logger.exception(
                    "Project dashboard metric failed: "
                    "project=%s metric=%s",
                    self.id,
                    metric.code,
                )
                continue

            section_name = (
                metric.section
                or _("Project Metrics")
            )

            section = section_map.setdefault(
                section_name,
                {
                    "name": section_name,
                    "sequence": assignment.sequence,
                    "metrics": [],
                },
            )

            section["sequence"] = min(
                section["sequence"],
                assignment.sequence,
            )

            section["metrics"].append(
                {
                    "id": assignment.id,
                    "name": metric.name,
                    "code": metric.code,
                    "unit": metric.unit,
                    "value": value,
                    "target": (
                        assignment.target_value
                        if assignment.target_value
                        else None
                    ),
                    "sequence": assignment.sequence,
                }
            )

        sections = sorted(
            section_map.values(),
            key=lambda item: (
                item["sequence"],
                item["name"],
            ),
        )

        for section in sections:
            section["metrics"] = sorted(
                section["metrics"],
                key=lambda item: (
                    item["sequence"],
                    item["name"],
                ),
            )

        currency = (
            self.company_id.currency_id
            if self.company_id
            else self.env.company.currency_id
        )

        return {
            "project_id": self.id,
            "project_name": self.display_name,
            "year": year,
            "quarter": quarter,
            "years": years,
            "start_date": (
                fields.Date.to_string(
                    self.start_date
                )
                if self.start_date
                else False
            ),
            "end_date": (
                fields.Date.to_string(
                    self.end_date
                )
                if self.end_date
                else False
            ),
            "currency_code": currency.name,
            "metadata": self._dashboard_metadata(),
            "sections": sections,
            "can_configure": self._dashboard_can_configure(),
        }
