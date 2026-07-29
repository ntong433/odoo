# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    @api.model
    def get_lhi_hub_dashboard_data(self):
        """Return only data visible under the caller's ACLs and record rules."""
        self.check_access("read")
        cards = []
        charts = []
        warnings = []
        today = fields.Date.context_today(self)
        month_start = fields.Date.start_of(today, "month")
        today_start = fields.Datetime.to_datetime(today)
        tomorrow_start = today_start + relativedelta(days=1)

        def add_count(key, label, model_name, domain, *, monetary=False, value=None):
            try:
                model = self.env[model_name]
                model.check_access("read")
                resolved = (
                    value(model) if callable(value) else model.search_count(domain)
                )
                cards.append(
                    {
                        "key": key,
                        "label": label,
                        "value": resolved,
                        "model": model_name,
                        "domain": domain,
                        "monetary": monetary,
                    }
                )
            except Exception:
                _logger.exception("HUB dashboard card failed safely: %s", key)
                warnings.append(
                    _("You do not have access to the %(label)s metric.")
                    % {"label": label}
                )

        internal_domain = [
            ("location_id.usage", "=", "internal"),
            ("quantity", ">", 0),
        ]
        add_count("hubs", _("Total HUBs"), "stock.warehouse", [])
        add_count(
            "stock_quantity",
            _("On-hand Stock Quantity"),
            "stock.quant",
            internal_domain,
            value=lambda model: sum(model.search(internal_domain).mapped("quantity")),
        )
        movement_today = [
            ("state", "=", "done"),
            ("date_done", ">=", today_start),
            ("date_done", "<", tomorrow_start),
        ]
        add_count(
            "receipts_today",
            _("Stock Receipts Today"),
            "stock.picking",
            movement_today + [("picking_type_id.code", "=", "incoming")],
        )
        add_count(
            "issues_today",
            _("External Issues Today"),
            "lhi.hub.external.issue",
            [("state", "=", "validated"), ("issue_date", "=", today)],
        )
        add_count(
            "transfers_today",
            _("Internal Transfers Today"),
            "stock.picking",
            movement_today + [("picking_type_id.code", "=", "internal")],
        )
        add_count(
            "pending_requests",
            _("Pending Stock Requests"),
            "lhi.hub.stock.request",
            [
                (
                    "state",
                    "not in",
                    ["closed", "rejected", "withdrawn", "draft"],
                )
            ],
        )
        add_count(
            "quantity_review",
            _("Requests Awaiting Quantity Review"),
            "lhi.hub.stock.request",
            [("state", "=", "quantity_review")],
        )
        add_count(
            "sign_preparation",
            _("Requests Awaiting LHI Sign Preparation"),
            "lhi.hub.stock.request",
            [("state", "=", "sign_preparation")],
        )
        for role, label in (
            ("operations_manager", _("Awaiting Operations Manager Signature")),
            ("director_operations", _("Awaiting Director of Operations Signature")),
            ("ned", _("Awaiting NED Signature")),
        ):
            add_count(
                f"signature_{role}",
                label,
                "lhi.hub.stock.request",
                [
                    ("state", "=", "signing"),
                    (
                        "approval_request_id.current_line_id.lhi_approval_role",
                        "=",
                        role,
                    ),
                ],
            )
        add_count(
            "fully_signed",
            _("Fully Signed Requests"),
            "lhi.hub.stock.request",
            [
                (
                    "state",
                    "in",
                    [
                        "approved",
                        "reserved",
                        "partially_dispatched",
                        "in_transit",
                        "partially_received",
                        "received",
                        "closed",
                    ],
                )
            ],
        )
        add_count(
            "awaiting_reservation",
            _("Requests Awaiting Stock Reservation"),
            "lhi.hub.stock.request",
            [("state", "=", "approved")],
        )
        add_count(
            "awaiting_dispatch",
            _("Requests Awaiting Dispatch"),
            "lhi.hub.stock.request",
            [("state", "in", ["reserved", "partially_dispatched"])],
        )
        add_count(
            "awaiting_receipt",
            _("Requests Awaiting Receipt"),
            "lhi.hub.stock.request",
            [
                (
                    "state",
                    "in",
                    ["in_transit", "partially_dispatched", "partially_received"],
                )
            ],
        )
        add_count(
            "stock_value",
            _("Operational Stock Value"),
            "stock.quant",
            internal_domain,
            monetary=True,
            value=lambda model: sum(
                model.search(internal_domain).mapped("lhi_operational_stock_value")
            ),
        )
        add_count(
            "requests_attention",
            _("Requests Awaiting Action"),
            "lhi.hub.stock.request",
            [
                (
                    "state",
                    "in",
                    [
                        "quantity_review",
                        "sign_preparation",
                        "signing",
                        "approved",
                        "reserved",
                        "partially_dispatched",
                        "in_transit",
                        "partially_received",
                    ],
                )
            ],
        )
        add_count(
            "consignments",
            _("Open Consignments"),
            "lhi.hub.consignment",
            [("state", "not in", ["closed", "cancelled"])],
        )
        add_count(
            "external_issues",
            _("External Issues This Month"),
            "lhi.hub.external.issue",
            [
                ("state", "=", "validated"),
                (
                    "issue_date",
                    ">=",
                    fields.Date.start_of(fields.Date.today(), "month"),
                ),
            ],
        )
        add_count(
            "active_leases",
            _("Active or Overdue Leases"),
            "lhi.hub.equipment.lease",
            [("state", "in", ["active", "overdue"])],
        )
        add_count(
            "low_stock",
            _("Low-stock Items"),
            "product.product",
            [("lhi_low_stock_threshold", ">", 0)],
            value=lambda model: self._lhi_low_stock_product_count(
                model, internal_domain, out_of_stock=False
            ),
        )
        add_count(
            "out_of_stock",
            _("Out-of-stock Items"),
            "product.product",
            [("lhi_hub_item_type", "!=", False)],
            value=lambda model: self._lhi_low_stock_product_count(
                model, internal_domain, out_of_stock=True
            ),
        )
        add_count(
            "expiring",
            _("Pharmaceutical Lots Expiring in 30 Days"),
            "stock.lot",
            [
                ("product_id.lhi_hub_item_type", "=", "pharmaceuticals"),
                ("expiration_date", ">=", fields.Datetime.now()),
                (
                    "expiration_date",
                    "<=",
                    fields.Datetime.now() + relativedelta(days=30),
                ),
            ],
        )
        add_count(
            "quarantine",
            _("Quarantined or Rejected Lots"),
            "stock.lot",
            [("lhi_quarantine_status", "in", ["quarantined", "rejected"])],
        )
        add_count(
            "expired",
            _("Expired Pharmaceutical Lots"),
            "stock.lot",
            [
                ("product_id.lhi_hub_item_type", "=", "pharmaceuticals"),
                ("expiration_date", "<", fields.Datetime.now()),
            ],
        )
        add_count(
            "integration_failures",
            _("Integration Failures"),
            "lhi.hub.stock.request",
            [("state", "=", "integration_error")],
        )
        add_count(
            "notification_failures",
            _("Notification Delivery Failures"),
            "lhi.hub.notification",
            [("state", "=", "failed")],
        )
        add_count(
            "revenue",
            _("Operational Revenue Recorded"),
            "lhi.hub.operational.revenue",
            [],
            monetary=True,
            value=lambda model: model.read_group([], ["amount:sum"], [])[0].get(
                "amount", 0.0
            ),
        )
        add_count(
            "lease_revenue_month",
            _("Lease Revenue This Month"),
            "lhi.hub.operational.revenue",
            [
                ("revenue_type", "=", "lease_payment"),
                ("transaction_date", ">=", month_start),
            ],
            monetary=True,
            value=lambda model: model.read_group(
                [
                    ("revenue_type", "=", "lease_payment"),
                    ("transaction_date", ">=", month_start),
                ],
                ["amount:sum"],
                [],
            )[0].get("amount", 0.0),
        )
        add_count(
            "issue_revenue_month",
            _("Issue Revenue This Month"),
            "lhi.hub.operational.revenue",
            [
                ("revenue_type", "=", "external_issue"),
                ("transaction_date", ">=", month_start),
            ],
            monetary=True,
            value=lambda model: model.read_group(
                [
                    ("revenue_type", "=", "external_issue"),
                    ("transaction_date", ">=", month_start),
                ],
                ["amount:sum"],
                [],
            )[0].get("amount", 0.0),
        )
        add_count(
            "outstanding",
            _("Outstanding Operational Amounts"),
            "lhi.hub.equipment.lease",
            [("state", "in", ["active", "overdue", "returned"])],
            monetary=True,
            value=lambda model: (
                sum(
                    model.search(
                        [("state", "in", ["active", "overdue", "returned"])]
                    ).mapped("outstanding_amount")
                )
                + sum(
                    self.env["lhi.hub.external.issue"]
                    .search(
                        [
                            ("state", "=", "validated"),
                            ("outstanding_amount", ">", 0),
                        ]
                    )
                    .mapped("outstanding_amount")
                )
            ),
        )
        add_count(
            "free_issues_month",
            _("Free Issues This Month"),
            "lhi.hub.external.issue",
            [
                ("state", "=", "validated"),
                ("issue_type", "=", "free"),
                ("issue_date", ">=", month_start),
            ],
        )
        add_count(
            "assets",
            _("Assets Assigned to HUBs"),
            "lhi.asset",
            [("hub_id", "!=", False)],
        )

        for key, label, model_name, groupby, base_domain in (
            (
                "requests_by_state",
                _("Stock Requests by Status"),
                "lhi.hub.stock.request",
                "state",
                [],
            ),
            (
                "revenue_by_type",
                _("Operational Revenue by Type"),
                "lhi.hub.operational.revenue",
                "revenue_type",
                [],
            ),
            (
                "stock_receipts_month",
                _("Stock Receipts by Month"),
                "stock.picking",
                "date_done:month",
                [
                    ("state", "=", "done"),
                    ("picking_type_id.code", "=", "incoming"),
                ],
            ),
            (
                "external_issues_month",
                _("External Issues by Month"),
                "lhi.hub.external.issue",
                "issue_date:month",
                [("state", "=", "validated")],
            ),
            (
                "internal_transfers_month",
                _("Internal Transfers by Month"),
                "stock.picking",
                "date_done:month",
                [
                    ("state", "=", "done"),
                    ("picking_type_id.code", "=", "internal"),
                ],
            ),
            (
                "expiring_month",
                _("Expiring Stock by Month"),
                "stock.lot",
                "expiration_date:month",
                [
                    ("product_id.lhi_hub_item_type", "=", "pharmaceuticals"),
                    ("expiration_date", ">=", fields.Datetime.now()),
                ],
            ),
            (
                "revenue_hub",
                _("Operational Revenue by HUB"),
                "lhi.hub.operational.revenue",
                "hub_id",
                [],
            ),
            (
                "lease_revenue_hub",
                _("Lease Revenue by HUB"),
                "lhi.hub.operational.revenue",
                "hub_id",
                [("revenue_type", "in", ["lease_payment", "lease_charge"])],
            ),
        ):
            try:
                model = self.env[model_name]
                model.check_access("read")
                aggregate = (
                    ["amount:sum"]
                    if model_name == "lhi.hub.operational.revenue"
                    else ["__count"]
                )
                rows = model.read_group(
                    base_domain, [groupby] + aggregate, [groupby], lazy=False
                )
                segments = []
                for row in rows:
                    grouped = row.get(groupby)
                    if isinstance(grouped, (tuple, list)):
                        grouped_value, grouped_label = grouped[0], grouped[1]
                    else:
                        grouped_value = grouped or False
                        grouped_label = grouped or _("Unspecified")
                        field = model._fields[groupby.split(":", 1)[0]]
                        if field.type == "selection" and grouped:
                            grouped_label = dict(
                                field._description_selection(self.env)
                            ).get(grouped, grouped)
                    segments.append(
                        {
                            "label": grouped_label,
                            "value": (
                                row.get("amount", 0.0)
                                if aggregate == ["amount:sum"]
                                else row.get("__count", 0)
                            ),
                            "domain": row.get(
                                "__domain",
                                base_domain + [(groupby, "=", grouped_value)],
                            ),
                        }
                    )
                charts.append(
                    {
                        "key": key,
                        "label": label,
                        "model": model_name,
                        "segments": segments,
                        "monetary": aggregate == ["amount:sum"],
                    }
                )
            except Exception:
                _logger.exception("HUB dashboard chart failed safely: %s", key)
                warnings.append(
                    _("You do not have access to the %(label)s analysis.")
                    % {"label": label}
                )

        manual_charts = (
            (
                "stock_value_hub",
                _("Stock Value by HUB"),
                "stock.quant",
                internal_domain,
                "warehouse_id",
                "lhi_operational_stock_value",
                True,
            ),
            (
                "stock_value_category",
                _("Stock Value by Category"),
                "stock.quant",
                internal_domain,
                "product_categ_id",
                "lhi_operational_stock_value",
                True,
            ),
            (
                "stock_quantity_category",
                _("Quantity by Category"),
                "stock.quant",
                internal_domain,
                "product_categ_id",
                "quantity",
                False,
            ),
            (
                "stock_value_donor",
                _("Stock Value by Donor"),
                "stock.quant",
                internal_domain,
                "lot_id.lhi_donor_id",
                "lhi_operational_stock_value",
                True,
            ),
            (
                "stock_value_project",
                _("Stock Value by Project"),
                "stock.quant",
                internal_domain,
                "lot_id.lhi_project_id",
                "lhi_operational_stock_value",
                True,
            ),
            (
                "issues_category",
                _("Issues by Item Category"),
                "lhi.hub.external.issue.line",
                [("issue_id.state", "=", "validated")],
                "product_id.categ_id",
                "quantity",
                False,
            ),
            (
                "issues_recipient",
                _("Issues by External-recipient Type"),
                "lhi.hub.external.issue",
                [("state", "=", "validated")],
                "recipient_id.lhi_recipient_type",
                False,
                False,
            ),
            (
                "revenue_category",
                _("Operational Revenue by Item Category"),
                "lhi.hub.external.issue.line",
                [
                    ("issue_id.state", "=", "validated"),
                    ("issue_id.issue_type", "=", "sale"),
                ],
                "product_id.categ_id",
                "line_total",
                True,
            ),
            (
                "most_issued",
                _("Most-issued Items"),
                "lhi.hub.external.issue.line",
                [("issue_id.state", "=", "validated")],
                "product_id",
                "quantity",
                False,
            ),
            (
                "approval_stage",
                _("HUB Requests by Approval Stage"),
                "lhi.hub.stock.request",
                [("state", "in", ["sign_preparation", "signing"])],
                "current_approval_stage",
                False,
                False,
            ),
            (
                "signature_stage",
                _("HUB Requests by Signature Stage"),
                "lhi.hub.stock.request",
                [("state", "=", "signing")],
                "current_signature_stage",
                False,
                False,
            ),
        )
        for (
            key,
            label,
            model_name,
            domain,
            group_path,
            value_field,
            monetary,
        ) in manual_charts:
            try:
                segments = self._lhi_dashboard_manual_segments(
                    model_name, domain, group_path, value_field
                )
                charts.append(
                    {
                        "key": key,
                        "label": label,
                        "model": model_name,
                        "segments": segments,
                        "monetary": monetary,
                    }
                )
            except Exception:
                _logger.exception("HUB dashboard chart failed safely: %s", key)
                warnings.append(
                    _("The %(label)s analysis is temporarily unavailable.")
                    % {"label": label}
                )

        try:
            leaseable_lots = self.env["stock.lot"].search(
                [("product_id.lhi_leaseable", "=", True)]
            )
            active_lines = self.env["lhi.hub.equipment.lease.line"].search(
                [("lease_id.state", "in", ["active", "overdue"])]
            )
            active_lots = active_lines.mapped("lot_id") & leaseable_lots
            available_lots = leaseable_lots - active_lots
            charts.append(
                {
                    "key": "equipment_utilization",
                    "label": _("Equipment Utilization"),
                    "model": "stock.lot",
                    "monetary": False,
                    "segments": [
                        {
                            "label": _("Currently on Lease"),
                            "value": len(active_lots),
                            "domain": [("id", "in", active_lots.ids)],
                        },
                        {
                            "label": _("Not on Active Lease"),
                            "value": len(available_lots),
                            "domain": [("id", "in", available_lots.ids)],
                        },
                    ],
                }
            )
        except Exception:
            _logger.exception(
                "HUB dashboard chart failed safely: equipment_utilization"
            )
            warnings.append(_("Equipment utilization is temporarily unavailable."))

        try:
            completed = self.env["lhi.hub.stock.request"].search(
                [
                    ("quantities_locked_at", "!=", False),
                    ("approval_completed_at", "!=", False),
                    (
                        "state",
                        "in",
                        [
                            "approved",
                            "reserved",
                            "partially_dispatched",
                            "in_transit",
                            "partially_received",
                            "received",
                            "closed",
                        ],
                    ),
                ]
            )
            hours = [
                (
                    request.approval_completed_at - request.quantities_locked_at
                ).total_seconds()
                / 3600
                for request in completed
                if request.approval_completed_at and request.quantities_locked_at
            ]
            charts.append(
                {
                    "key": "average_approval_duration",
                    "label": _("Average Approval and Signing Duration (hours)"),
                    "model": "lhi.hub.stock.request",
                    "monetary": False,
                    "segments": [
                        {
                            "label": _("Completed signed routes"),
                            "value": sum(hours) / len(hours) if hours else 0,
                            "domain": [("id", "in", completed.ids)],
                        }
                    ],
                }
            )
        except Exception:
            _logger.exception(
                "HUB dashboard chart failed safely: average_approval_duration"
            )
            warnings.append(_("Average approval duration is temporarily unavailable."))

        return {
            "cards": cards,
            "charts": charts,
            "warnings": warnings,
            "currency": self.env.company.currency_id.symbol,
        }

    @api.model
    def _lhi_low_stock_product_count(
        self, product_model, quant_domain, *, out_of_stock=False
    ):
        products = product_model.search([("lhi_hub_item_type", "!=", False)])
        quantities = {}
        for quant in self.env["stock.quant"].search(quant_domain):
            quantities[quant.product_id.id] = (
                quantities.get(quant.product_id.id, 0.0) + quant.quantity
            )
        if out_of_stock:
            return len(
                products.filtered(lambda product: quantities.get(product.id, 0.0) <= 0)
            )
        return len(
            products.filtered(
                lambda product: (
                    product.lhi_low_stock_threshold > 0
                    and 0
                    < quantities.get(product.id, 0.0)
                    <= product.lhi_low_stock_threshold
                )
            )
        )

    @api.model
    def _lhi_dashboard_manual_segments(
        self, model_name, domain, group_path, value_field=False
    ):
        model = self.env[model_name]
        model.check_access("read")
        grouped = {}
        for record in model.search(domain):
            value = record
            for field_name in group_path.split("."):
                value = value[field_name] if value else False
            if hasattr(value, "ids"):
                key = (value._name, value.id) if value else (False, False)
                label = value.display_name if value else _("Unspecified")
            else:
                key = value or False
                label = value or _("Unspecified")
            bucket = grouped.setdefault(key, {"label": label, "value": 0.0, "ids": []})
            bucket["value"] += record[value_field] if value_field else 1
            bucket["ids"].append(record.id)
        return [
            {
                "label": bucket["label"],
                "value": bucket["value"],
                "domain": [("id", "in", bucket["ids"])],
            }
            for bucket in sorted(
                grouped.values(), key=lambda item: item["value"], reverse=True
            )
        ]
