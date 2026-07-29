# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class ResPartner(models.Model):
    _inherit = "res.partner"

    lhi_external_recipient = fields.Boolean(
        string="HUB External Recipient", tracking=True
    )
    lhi_recipient_type = fields.Selection(
        [
            ("beneficiary", "Beneficiary"),
            ("individual_customer", "Individual Customer"),
            ("household", "Household"),
            ("organization", "Organisation"),
            ("health_facility", "Health Facility"),
            ("government", "Government Institution"),
            ("partner", "Implementing Partner"),
            ("community_representative", "Community Representative"),
            ("lease_customer", "Paying Lease Customer"),
            ("other", "Other"),
        ]
    )
    lhi_beneficiary_reference = fields.Char(
        index=True,
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_community = fields.Char(
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin"
    )
    lhi_lga = fields.Char(
        string="LGA",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_state = fields.Char(
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin"
    )
    lhi_recipient_consent_reference = fields.Char(
        help="Reference to the consent evidence stored in SharePoint; do not put "
        "identity-document bytes in this field.",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_project_id = fields.Many2one(
        "lhi.project",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_programme_id = fields.Many2one(
        "lhi.programme",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_activity_id = fields.Many2one(
        "lhi.workplan.activity",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )
    lhi_recipient_supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_external_recipient_attachment_rel",
        "partner_id",
        "attachment_id",
        groups="lhi_security.group_lhi_warehouse_officer,lhi_security.group_lhi_operations_officer,lhi_security.group_lhi_operations_manager,lhi_security.group_lhi_director_operations,lhi_security.group_lhi_system_auditor,lhi_security.group_lhi_erp_admin",
    )


class LhiHubPaymentMethod(models.Model):
    _name = "lhi.hub.payment.method"
    _description = "HUB Operational Payment Method"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_reference = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company")

    _code_company_unique = models.Constraint(
        "unique(code, company_id)",
        "Payment method codes must be unique per company.",
    )


class LhiHubOperationalRevenue(models.Model):
    _name = "lhi.hub.operational.revenue"
    _description = "HUB Operational Revenue Ledger"
    _order = "transaction_date desc, id desc"

    name = fields.Char(required=True, readonly=True)
    transaction_date = fields.Date(required=True, readonly=True)
    hub_id = fields.Many2one(
        "stock.warehouse", required=True, readonly=True, ondelete="restrict"
    )
    source_model = fields.Char(required=True, readonly=True, index=True)
    source_id = fields.Integer(required=True, readonly=True, index=True)
    source_reference = fields.Char(required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True, ondelete="restrict")
    officer_id = fields.Many2one("res.users", required=True, readonly=True)
    payment_method_id = fields.Many2one(
        "lhi.hub.payment.method", readonly=True, ondelete="restrict"
    )
    payment_reference = fields.Char(readonly=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True)
    amount = fields.Monetary(required=True, readonly=True)
    revenue_type = fields.Selection(
        [
            ("external_issue", "External Issue"),
            ("lease_payment", "Lease Payment"),
            ("lease_charge", "Lease Charge"),
            ("reversal", "Reversal"),
        ],
        required=True,
        readonly=True,
    )
    reversed_entry_id = fields.Many2one(
        "lhi.hub.operational.revenue", readonly=True, ondelete="restrict"
    )
    company_id = fields.Many2one(related="hub_id.company_id", store=True, readonly=True)

    _source_unique = models.Constraint(
        "unique(source_model, source_id, revenue_type)",
        "This operational revenue event has already been recorded.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("lhi_hub_revenue_system") is not LHI_HUB_SYSTEM_TOKEN:
            raise AccessError(
                _("Operational revenue is created only by HUB workflows.")
            )
        records = super().create(vals_list)
        for record in records:
            self.env["lhi.audit.log"].create_event(
                event_type="hub_operation",
                res_model=record._name,
                res_id=record.id,
                description=_("Recorded immutable HUB operational revenue %s.")
                % record.name,
            )
        return records

    def write(self, vals):
        raise AccessError(_("Operational revenue entries are immutable."))

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise AccessError(_("Operational revenue entries are immutable."))
        return super().unlink()


class LhiHubExternalIssue(models.Model):
    _name = "lhi.hub.external.issue"
    _description = "HUB External Stock Issue"
    _inherit = ["mail.thread", "mail.activity.mixin", "lhi.hub.access.mixin"]
    _order = "issue_date desc, id desc"

    name = fields.Char(
        string="Issue Number", required=True, copy=False, default=lambda self: _("New")
    )
    hub_id = fields.Many2one(
        "stock.warehouse", required=True, tracking=True, ondelete="restrict"
    )
    recipient_id = fields.Many2one(
        "res.partner",
        required=True,
        tracking=True,
        domain=[("lhi_external_recipient", "=", True)],
        ondelete="restrict",
    )
    issue_type = fields.Selection(
        [
            ("free", "Free Distribution"),
            ("sale", "Cost-recovery Sale"),
            ("programme", "Programme Distribution"),
            ("replacement", "Replacement"),
            ("return", "Recipient Return"),
            ("reversal", "Reversal"),
        ],
        required=True,
        default="free",
        tracking=True,
    )
    issue_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True
    )
    project_id = fields.Many2one("lhi.project")
    programme_id = fields.Many2one("lhi.programme")
    award_id = fields.Many2one("lhi.award", string="Grant or Award")
    donor_id = fields.Many2one("res.partner")
    activity_id = fields.Many2one("lhi.workplan.activity")
    purpose = fields.Text(required=True)
    distribution_event = fields.Boolean(
        help="Use for mass distributions supported by a bounded beneficiary list."
    )
    distribution_event_name = fields.Char()
    distribution_location = fields.Char()
    beneficiary_count = fields.Integer()
    beneficiary_ids = fields.Many2many(
        "res.partner",
        "lhi_hub_issue_beneficiary_rel",
        "issue_id",
        "partner_id",
        domain=[("lhi_external_recipient", "=", True)],
    )
    beneficiary_list_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_hub_issue_beneficiary_attachment_rel",
        "issue_id",
        "attachment_id",
    )
    officer_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, readonly=True
    )
    line_ids = fields.One2many("lhi.hub.external.issue.line", "issue_id", copy=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    total_amount = fields.Monetary(compute="_compute_amounts", store=True)
    amount_received = fields.Monetary(default=0.0, tracking=True)
    outstanding_amount = fields.Monetary(compute="_compute_amounts", store=True)
    payment_method_id = fields.Many2one("lhi.hub.payment.method", ondelete="restrict")
    payment_reference = fields.Char()
    supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_hub_external_issue_attachment_rel",
        "issue_id",
        "attachment_id",
    )
    picking_id = fields.Many2one("stock.picking", readonly=True, ondelete="restrict")
    reversal_of_id = fields.Many2one(
        "lhi.hub.external.issue", readonly=True, ondelete="restrict"
    )
    reversal_id = fields.Many2one(
        "lhi.hub.external.issue", readonly=True, ondelete="restrict"
    )
    reversal_reason = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("reversed", "Reversed"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(related="hub_id.company_id", store=True, readonly=True)

    @api.depends("line_ids.line_total", "amount_received")
    def _compute_amounts(self):
        for issue in self:
            issue.total_amount = sum(issue.line_ids.mapped("line_total"))
            issue.outstanding_amount = issue.total_amount - issue.amount_received

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "draft") != "draft"
                or vals.get("picking_id")
                or vals.get("reversal_id")
                or vals.get("reversal_of_id")
            ) and self.env.context.get(
                "lhi_hub_issue_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(
                    _("External-issue workflow fields are system-managed.")
                )
            vals["officer_id"] = self.env.user.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.external.issue"
                ) or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if (
            "state" in vals
            and self.env.context.get("lhi_hub_issue_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Use the external-issue workflow to change status."))
        if (
            any(issue.state != "draft" for issue in self)
            and self.env.context.get("lhi_hub_issue_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            if set(vals).issubset({"reversal_reason"}):
                for issue in self:
                    issue._lhi_assert_hub_access(issue.hub_id, management=True)
            else:
                raise AccessError(
                    _("Validated external issues are immutable; create a reversal.")
                )
        return super().write(vals)

    def unlink(self):
        if any(issue.state != "draft" for issue in self):
            raise AccessError(_("Validated external issues cannot be deleted."))
        return super().unlink()

    def _lhi_validate_business_data(self):
        self.ensure_one()
        if not self.recipient_id.lhi_external_recipient:
            raise ValidationError(_("Select a registered external recipient."))
        if not self.line_ids:
            raise ValidationError(_("Add at least one issue line."))
        if self.distribution_event:
            if self.issue_type not in ("free", "programme"):
                raise ValidationError(
                    _("Mass distributions must be free or programme issues.")
                )
            if self.beneficiary_count <= 0:
                raise ValidationError(_("Record the beneficiary count."))
            if not self.beneficiary_ids and not self.beneficiary_list_document_ids:
                raise ValidationError(
                    _(
                        "Attach a beneficiary list or select structured "
                        "beneficiary records."
                    )
                )
        if self.issue_type == "sale":
            if self.total_amount <= 0:
                raise ValidationError(_("A cost-recovery sale must have a value."))
            if self.amount_received < 0 or self.amount_received > self.total_amount:
                raise ValidationError(
                    _("The amount received is outside the valid range.")
                )
            if self.amount_received and not self.payment_method_id:
                raise ValidationError(_("Select the payment method."))
            if (
                self.payment_method_id.requires_reference
                and self.amount_received
                and not self.payment_reference
            ):
                raise ValidationError(_("A payment reference is required."))
        elif self.amount_received:
            raise ValidationError(
                _("Only cost-recovery sales may record an amount received.")
            )
        for line in self.line_ids:
            line._lhi_validate_line()

    def action_validate(self):
        stock_service = self.env["lhi.hub.stock.service"]
        customer = self.env.ref("stock.stock_location_customers")
        for original in self:
            issue = original.try_lock_for_update()
            if not issue:
                raise UserError(_("This issue is being processed by another user."))
            issue._lhi_assert_hub_access(issue.hub_id)
            if issue.state != "draft":
                raise UserError(_("Only a draft external issue can be validated."))
            issue._lhi_validate_business_data()
            is_return = issue.issue_type in ("return", "reversal")
            source = (
                customer
                if is_return
                else issue.hub_id.lhi_default_dispatch_location_id
                or issue.hub_id.lot_stock_id
            )
            destination = (
                issue.hub_id.lhi_returns_location_id or issue.hub_id.lot_stock_id
                if is_return
                else customer
            )
            picking_type = (
                issue.hub_id.in_type_id if is_return else issue.hub_id.out_type_id
            )
            specs = [
                {
                    "product": line.product_id,
                    "quantity": line.quantity,
                    "uom": line.uom_id,
                    "lot": line.lot_id,
                    "values": {
                        "lhi_external_issue_line_id": line.id,
                        "lhi_project_id": issue.project_id.id,
                        "lhi_donor_id": issue.donor_id.id,
                        "lhi_activity_id": issue.activity_id.id,
                    },
                }
                for line in issue.line_ids
            ]
            picking = stock_service._lhi_create_picking(
                picking_type=picking_type,
                source_location=source,
                destination_location=destination,
                origin=issue.name,
                move_specs=specs,
                picking_values={
                    "lhi_hub_document_type": "external_issue",
                    "lhi_external_issue_id": issue.id,
                },
                reserve=not is_return,
            )
            if is_return:
                issue._lhi_assign_return_lots(picking)
            stock_service._lhi_validate_picking(picking)
            issue.with_context(lhi_hub_issue_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"picking_id": picking.id, "state": "validated"}
            )
            if issue.amount_received:
                issue._lhi_create_revenue()
            issue.message_post(
                body=_("External issue validated through stock movement %s.")
                % picking.name
            )
        return True

    def _lhi_assign_return_lots(self, picking):
        self.ensure_one()
        for line, move in zip(self.line_ids, picking.move_ids):
            if line.product_id.tracking == "none":
                continue
            self.env["stock.move.line"].create(
                {
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.uom_id.id,
                    "quantity": line.quantity,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "lot_id": line.lot_id.id,
                    "company_id": picking.company_id.id,
                    "picked": True,
                }
            )

    def _lhi_create_revenue(self):
        self.ensure_one()
        return (
            self.env["lhi.hub.operational.revenue"]
            .with_context(lhi_hub_revenue_system=LHI_HUB_SYSTEM_TOKEN)
            .create(
                {
                    "name": _("External issue %s") % self.name,
                    "transaction_date": self.issue_date,
                    "hub_id": self.hub_id.id,
                    "source_model": self._name,
                    "source_id": self.id,
                    "source_reference": self.name,
                    "partner_id": self.recipient_id.id,
                    "officer_id": self.env.user.id,
                    "payment_method_id": self.payment_method_id.id,
                    "payment_reference": self.payment_reference,
                    "currency_id": self.currency_id.id,
                    "amount": self.amount_received,
                    "revenue_type": "external_issue",
                }
            )
        )

    def action_reverse(self):
        for issue in self:
            issue._lhi_assert_hub_access(issue.hub_id, management=True)
            if issue.state != "validated" or issue.reversal_id:
                raise UserError(
                    _("Only an unreversed validated issue can be reversed.")
                )
            if not (issue.reversal_reason or "").strip():
                raise ValidationError(_("Record the reversal reason first."))
            reversal = self.create(
                {
                    "hub_id": issue.hub_id.id,
                    "recipient_id": issue.recipient_id.id,
                    "issue_type": "reversal",
                    "purpose": _("Reversal of %(reference)s: %(reason)s")
                    % {"reference": issue.name, "reason": issue.reversal_reason},
                    "project_id": issue.project_id.id,
                    "programme_id": issue.programme_id.id,
                    "award_id": issue.award_id.id,
                    "donor_id": issue.donor_id.id,
                    "activity_id": issue.activity_id.id,
                    "reversal_of_id": issue.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "quantity": line.quantity,
                                "uom_id": line.uom_id.id,
                                "lot_id": line.lot_id.id,
                                "unit_price": 0,
                            },
                        )
                        for line in issue.line_ids
                    ],
                }
            )
            reversal.action_validate()
            issue.with_context(lhi_hub_issue_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": "reversed", "reversal_id": reversal.id}
            )
            if issue.amount_received:
                original_revenue = self.env["lhi.hub.operational.revenue"].search(
                    [
                        ("source_model", "=", issue._name),
                        ("source_id", "=", issue.id),
                        ("revenue_type", "=", "external_issue"),
                    ],
                    limit=1,
                )
                self.env["lhi.hub.operational.revenue"].with_context(
                    lhi_hub_revenue_system=LHI_HUB_SYSTEM_TOKEN
                ).create(
                    {
                        "name": _("Reversal of %s") % issue.name,
                        "transaction_date": fields.Date.context_today(self),
                        "hub_id": issue.hub_id.id,
                        "source_model": reversal._name,
                        "source_id": reversal.id,
                        "source_reference": reversal.name,
                        "partner_id": issue.recipient_id.id,
                        "officer_id": self.env.user.id,
                        "currency_id": issue.currency_id.id,
                        "amount": -issue.amount_received,
                        "revenue_type": "reversal",
                        "reversed_entry_id": original_revenue.id,
                    }
                )
        return True


class LhiHubExternalIssueLine(models.Model):
    _name = "lhi.hub.external.issue.line"
    _description = "HUB External Issue Line"
    _order = "id"

    issue_id = fields.Many2one(
        "lhi.hub.external.issue", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    item_description = fields.Char(related="product_id.display_name")
    category_id = fields.Many2one(related="product_id.categ_id")
    uom_id = fields.Many2one("uom.uom", required=True)
    quantity = fields.Float(required=True, digits="Product Unit of Measure")
    lot_id = fields.Many2one(
        "stock.lot",
        domain="[('product_id', '=', product_id), ('company_id', 'in', [False, company_id])]",
        ondelete="restrict",
    )
    available_quantity = fields.Float(compute="_compute_available_quantity")
    expiry_date = fields.Datetime(related="lot_id.expiration_date")
    purpose_remarks = fields.Text()
    unit_price = fields.Monetary(default=0.0)
    discount_percent = fields.Float(default=0.0)
    line_total = fields.Monetary(compute="_compute_line_total", store=True)
    currency_id = fields.Many2one(related="issue_id.currency_id", store=True)
    company_id = fields.Many2one(related="issue_id.company_id", store=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.lhi_operational_unit_value

    @api.depends("quantity", "unit_price", "discount_percent")
    def _compute_line_total(self):
        for line in self:
            line.line_total = (
                line.quantity
                * line.unit_price
                * (1.0 - min(max(line.discount_percent, 0.0), 100.0) / 100.0)
            )

    @api.depends(
        "product_id",
        "lot_id",
        "issue_id.hub_id",
        "issue_id.hub_id.lot_stock_id",
    )
    def _compute_available_quantity(self):
        for line in self:
            if not line.product_id or not line.issue_id.hub_id:
                line.available_quantity = 0.0
                continue
            line.available_quantity = self.env["stock.quant"]._get_available_quantity(
                line.product_id,
                line.issue_id.hub_id.lot_stock_id,
                lot_id=line.lot_id,
                strict=False,
            )

    def _lhi_validate_line(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise ValidationError(_("Issue quantities must be positive."))
        if self.unit_price < 0 or not 0 <= self.discount_percent <= 100:
            raise ValidationError(_("Price and discount values are invalid."))
        if self.product_id.tracking != "none" and not self.lot_id:
            raise ValidationError(
                _("Select a lot or serial for %s.") % self.product_id.display_name
            )
        if self.lot_id and self.issue_id.issue_type not in ("return", "reversal"):
            self.lot_id._lhi_assert_issuable()

    def write(self, vals):
        if any(line.issue_id.state != "draft" for line in self):
            raise AccessError(_("Validated external issue lines are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(line.issue_id.state != "draft" for line in self):
            raise AccessError(_("Validated external issue lines cannot be deleted."))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            issue = self.env["lhi.hub.external.issue"].browse(vals.get("issue_id"))
            if issue.exists():
                issue._lhi_assert_hub_access(issue.hub_id)
                if issue.state != "draft":
                    raise AccessError(
                        _("Lines can be added only to draft external issues.")
                    )
        return super().create(vals_list)
