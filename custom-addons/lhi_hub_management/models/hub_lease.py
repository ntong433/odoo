# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class LhiHubEquipmentLease(models.Model):
    _name = "lhi.hub.equipment.lease"
    _description = "HUB Equipment Lease"
    _inherit = ["mail.thread", "mail.activity.mixin", "lhi.hub.access.mixin"]
    _order = "start_date desc, id desc"

    name = fields.Char(
        string="Lease Number", required=True, copy=False, default=lambda self: _("New")
    )
    hub_id = fields.Many2one(
        "stock.warehouse", required=True, tracking=True, ondelete="restrict"
    )
    lessee_id = fields.Many2one(
        "res.partner",
        required=True,
        tracking=True,
        domain=[("lhi_external_recipient", "=", True)],
        ondelete="restrict",
    )
    start_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True
    )
    expected_return_date = fields.Date(required=True, tracking=True)
    actual_return_date = fields.Date(readonly=True, tracking=True)
    purpose = fields.Text(required=True)
    charging_basis = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("fixed", "Fixed Amount"),
            ("per_usage", "Per Usage"),
            ("no_charge", "No-charge Programme Deployment"),
        ],
        required=True,
        default="fixed",
        tracking=True,
    )
    project_id = fields.Many2one("lhi.project")
    programme_id = fields.Many2one("lhi.programme")
    award_id = fields.Many2one("lhi.award", string="Grant or Award")
    activity_id = fields.Many2one("lhi.workplan.activity")
    officer_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, readonly=True
    )
    line_ids = fields.One2many("lhi.hub.equipment.lease.line", "lease_id", copy=True)
    payment_ids = fields.One2many("lhi.hub.lease.payment", "lease_id")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    lease_amount = fields.Monetary(compute="_compute_amounts", store=True)
    deposit_amount = fields.Monetary(default=0.0, tracking=True)
    damage_charge = fields.Monetary(compute="_compute_amounts", store=True)
    late_charge = fields.Monetary(default=0.0, tracking=True)
    waived_charge = fields.Monetary(default=0.0, tracking=True)
    waiver_indicator = fields.Boolean(tracking=True)
    waiver_reason = fields.Text()
    total_due = fields.Monetary(compute="_compute_amounts", store=True)
    total_paid = fields.Monetary(compute="_compute_amounts", store=True)
    outstanding_amount = fields.Monetary(compute="_compute_amounts", store=True)
    charge_waiver_reason = fields.Text()
    supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_hub_equipment_lease_attachment_rel",
        "lease_id",
        "attachment_id",
    )
    release_picking_id = fields.Many2one(
        "stock.picking", readonly=True, ondelete="restrict"
    )
    return_picking_id = fields.Many2one(
        "stock.picking", readonly=True, ondelete="restrict"
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("overdue", "Overdue"),
            ("returned", "Returned"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(related="hub_id.company_id", store=True, readonly=True)

    @api.depends(
        "line_ids.agreed_amount",
        "line_ids.damage_charge",
        "deposit_amount",
        "waived_charge",
        "late_charge",
        "payment_ids.amount",
        "payment_ids.state",
    )
    def _compute_amounts(self):
        for lease in self:
            lease.lease_amount = sum(lease.line_ids.mapped("agreed_amount"))
            lease.damage_charge = sum(lease.line_ids.mapped("damage_charge"))
            lease.total_due = max(
                lease.lease_amount
                + lease.damage_charge
                + lease.late_charge
                - lease.waived_charge,
                0,
            )
            lease.total_paid = sum(
                lease.payment_ids.filtered(
                    lambda payment: payment.state == "posted"
                ).mapped("amount")
            )
            lease.outstanding_amount = lease.total_due - lease.total_paid

    @api.constrains(
        "start_date",
        "expected_return_date",
        "waived_charge",
        "damage_charge",
        "late_charge",
        "waiver_indicator",
        "waiver_reason",
    )
    def _check_dates_and_waiver(self):
        for lease in self:
            if lease.expected_return_date < lease.start_date:
                raise ValidationError(
                    _("Expected return cannot be before the lease start.")
                )
            if lease.waived_charge < 0 or lease.waived_charge > lease.damage_charge:
                raise ValidationError(_("The damage-charge waiver is invalid."))
            if lease.waived_charge and not (lease.charge_waiver_reason or "").strip():
                raise ValidationError(_("A charge-waiver reason is required."))
            if lease.late_charge < 0:
                raise ValidationError(_("Late charges cannot be negative."))
            if lease.waiver_indicator and not (lease.waiver_reason or "").strip():
                raise ValidationError(_("A lease waiver reason is required."))
            if lease.charging_basis == "no_charge" and not lease.waiver_indicator:
                raise ValidationError(
                    _("No-charge deployments require a documented waiver.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "draft") != "draft"
                or vals.get("release_picking_id")
                or vals.get("return_picking_id")
                or vals.get("actual_return_date")
            ) and self.env.context.get(
                "lhi_hub_lease_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(_("Lease workflow fields are system-managed."))
            vals["officer_id"] = self.env.user.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.equipment.lease"
                ) or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if (
            "state" in vals
            and self.env.context.get("lhi_hub_lease_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Use the equipment-lease workflow to change status."))
        if {
            "waived_charge",
            "charge_waiver_reason",
            "waiver_indicator",
            "waiver_reason",
        }.intersection(vals):
            for lease in self:
                lease._lhi_assert_hub_access(lease.hub_id, management=True)
        material = {
            "hub_id",
            "lessee_id",
            "start_date",
            "expected_return_date",
            "charging_basis",
            "line_ids",
            "currency_id",
        }
        if material.intersection(vals) and any(
            lease.state != "draft" for lease in self
        ):
            raise ValidationError(_("Released lease terms are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(lease.state != "draft" for lease in self):
            raise AccessError(_("Released leases cannot be deleted."))
        return super().unlink()

    def action_release_equipment(self):
        service = self.env["lhi.hub.stock.service"]
        customer = self.env.ref("stock.stock_location_customers")
        for original in self:
            lease = original.try_lock_for_update()
            if not lease:
                raise UserError(_("This lease is being processed by another user."))
            lease._lhi_assert_hub_access(lease.hub_id)
            if lease.state != "draft":
                raise UserError(_("Only a draft lease can be released."))
            if not lease.line_ids:
                raise ValidationError(_("Add at least one lease item."))
            for line in lease.line_ids:
                line._lhi_validate_release()
            if (
                lease.lease_amount > 0
                and not lease.payment_ids.filtered(
                    lambda payment: payment.state == "posted"
                )
                and not lease.waiver_indicator
            ):
                raise ValidationError(
                    _(
                        "Record a payment or an authorized operational waiver "
                        "before equipment release."
                    )
                )
            picking = service._lhi_create_picking(
                picking_type=lease.hub_id.out_type_id,
                source_location=(
                    lease.hub_id.lhi_default_dispatch_location_id
                    or lease.hub_id.lot_stock_id
                ),
                destination_location=customer,
                origin=lease.name,
                move_specs=[
                    {
                        "product": line.product_id,
                        "quantity": 1,
                        "uom": line.product_id.uom_id,
                        "lot": line.lot_id,
                        "values": {
                            "lhi_lease_line_id": line.id,
                            "lhi_project_id": lease.project_id.id,
                            "lhi_activity_id": lease.activity_id.id,
                        },
                    }
                    for line in lease.line_ids
                ],
                picking_values={
                    "lhi_equipment_lease_id": lease.id,
                    "lhi_hub_document_type": "lease_release",
                    "lhi_project_id": lease.project_id.id,
                },
                reserve=True,
            )
            service._lhi_validate_picking(picking)
            lease.with_context(lhi_hub_lease_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"release_picking_id": picking.id, "state": "active"}
            )
            lease.message_post(
                body=_("Lease equipment released through stock movement %s.")
                % picking.name
            )
        return True

    def action_receive_return(self):
        service = self.env["lhi.hub.stock.service"]
        customer = self.env.ref("stock.stock_location_customers")
        for original in self:
            lease = original.try_lock_for_update()
            if not lease:
                raise UserError(_("This lease is being processed by another user."))
            lease._lhi_assert_hub_access(lease.hub_id)
            if lease.state not in ("active", "overdue"):
                raise UserError(_("Only active or overdue leases can be returned."))
            if lease.return_picking_id:
                raise UserError(_("The lease return has already been posted."))
            for line in lease.line_ids:
                if not line.return_condition:
                    raise ValidationError(
                        _("Record the return condition for every serial.")
                    )
            picking = service._lhi_create_picking(
                picking_type=lease.hub_id.in_type_id,
                source_location=customer,
                destination_location=(
                    lease.hub_id.lhi_returns_location_id or lease.hub_id.lot_stock_id
                ),
                origin=_("Return %s") % lease.name,
                move_specs=[
                    {
                        "product": line.product_id,
                        "quantity": 1,
                        "uom": line.product_id.uom_id,
                        "values": {"lhi_lease_line_id": line.id},
                    }
                    for line in lease.line_ids
                ],
                picking_values={
                    "lhi_equipment_lease_id": lease.id,
                    "lhi_hub_document_type": "lease_return",
                },
            )
            for move in picking.move_ids:
                lot = move.lhi_lease_line_id.lot_id
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": 1,
                        "location_id": picking.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                        "lot_id": lot.id,
                        "company_id": picking.company_id.id,
                        "picked": True,
                    }
                )
            service._lhi_validate_picking(picking)
            lease.line_ids.with_context(
                lhi_hub_lease_line_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"returned": True})
            lease.with_context(lhi_hub_lease_system=LHI_HUB_SYSTEM_TOKEN).write(
                {
                    "return_picking_id": picking.id,
                    "actual_return_date": fields.Date.context_today(self),
                    "state": "returned",
                }
            )
            if lease.outstanding_amount > lease.currency_id.rounding:
                lease._lhi_queue_notification(
                    "outstanding_lease_amount",
                    _(
                        "Equipment lease %(lease)s was returned with an "
                        "outstanding operational amount of %(amount)s."
                    )
                    % {
                        "lease": lease.name,
                        "amount": lease.outstanding_amount,
                    },
                    lease.hub_id.lhi_operations_manager_id | lease.officer_id,
                )
        return True

    def action_close(self):
        for lease in self:
            lease._lhi_assert_hub_access(lease.hub_id, management=True)
            if lease.state != "returned":
                raise UserError(_("Receive the equipment before closing the lease."))
            if lease.outstanding_amount > lease.currency_id.rounding:
                raise ValidationError(
                    _(
                        "Outstanding operational lease charges must be settled or waived."
                    )
                )
            lease.with_context(lhi_hub_lease_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": "closed"}
            )
        return True

    @api.model
    def _cron_mark_overdue(self):
        overdue = self.search(
            [
                ("state", "=", "active"),
                ("expected_return_date", "<", fields.Date.context_today(self)),
            ],
            limit=200,
        )
        overdue.with_context(lhi_hub_lease_system=LHI_HUB_SYSTEM_TOKEN).write(
            {"state": "overdue"}
        )
        for lease in overdue:
            lease._lhi_queue_notification(
                "lease_overdue",
                _("Equipment lease %s is overdue.") % lease.name,
                lease.hub_id.lhi_operations_manager_id,
            )
        return True

    def _lhi_queue_notification(self, event_type, message, users):
        self.ensure_one()
        return self.env["lhi.hub.notification"].enqueue(
            source=self,
            event_type=event_type,
            message=message,
            users=users,
        )


class LhiHubEquipmentLeaseLine(models.Model):
    _name = "lhi.hub.equipment.lease.line"
    _description = "HUB Equipment Lease Line"
    _order = "id"

    lease_id = fields.Many2one(
        "lhi.hub.equipment.lease", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    lot_id = fields.Many2one(
        "stock.lot",
        required=True,
        ondelete="restrict",
        domain="[('product_id', '=', product_id), ('company_id', 'in', [False, company_id])]",
    )
    daily_rate = fields.Monetary(default=0.0)
    weekly_rate = fields.Monetary(default=0.0)
    monthly_rate = fields.Monetary(default=0.0)
    per_usage_rate = fields.Monetary(default=0.0)
    agreed_amount = fields.Monetary(required=True, default=0.0)
    release_condition = fields.Selection(
        [
            ("new", "New"),
            ("good", "Good"),
            ("fair", "Fair"),
        ],
        required=True,
        default="good",
    )
    return_condition = fields.Selection(
        [
            ("good", "Good"),
            ("fair", "Fair"),
            ("damaged", "Damaged"),
            ("lost", "Lost"),
        ]
    )
    return_notes = fields.Text()
    damage_charge = fields.Monetary(default=0.0)
    returned = fields.Boolean(readonly=True)
    currency_id = fields.Many2one(related="lease_id.currency_id", store=True)
    company_id = fields.Many2one(related="lease_id.company_id", store=True)

    _lease_lot_unique = models.Constraint(
        "unique(lease_id, lot_id)",
        "A serial can occur only once on a lease.",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.daily_rate = self.product_id.lhi_lease_daily_rate

    def _lhi_validate_release(self):
        self.ensure_one()
        if (
            not self.product_id.lhi_leaseable
            or self.product_id.tracking != "serial"
            or self.lot_id.product_id != self.product_id
        ):
            raise ValidationError(
                _("%s must be leaseable, serial-tracked equipment.")
                % self.product_id.display_name
            )
        if self.agreed_amount < 0 or self.damage_charge < 0:
            raise ValidationError(_("Lease amounts cannot be negative."))
        locked = self.lot_id.try_lock_for_update()
        if not locked:
            raise UserError(_("Serial %s is being allocated.") % self.lot_id.name)
        other = self.search_count(
            [
                ("lot_id", "=", self.lot_id.id),
                ("lease_id.state", "in", ["active", "overdue"]),
                ("id", "!=", self.id),
            ]
        )
        if other:
            raise ValidationError(
                _("Serial %s already has an active lease.") % self.lot_id.name
            )
        self.lot_id._lhi_assert_issuable()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            lease = self.env["lhi.hub.equipment.lease"].browse(vals.get("lease_id"))
            if lease.exists():
                lease._lhi_assert_hub_access(lease.hub_id)
                if lease.state != "draft":
                    raise AccessError(_("Lines can be added only to draft leases."))
            if (
                vals.get("returned")
                and self.env.context.get("lhi_hub_lease_line_system")
                is not LHI_HUB_SYSTEM_TOKEN
            ):
                raise AccessError(_("Return status is workflow-managed."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            "returned" in vals
            and self.env.context.get("lhi_hub_lease_line_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Return status is controlled by stock validation."))
        if (
            any(line.lease_id.state != "draft" for line in self)
            and self.env.context.get("lhi_hub_lease_line_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            allowed = {"return_condition", "return_notes", "damage_charge"}
            if not set(vals).issubset(allowed):
                raise AccessError(_("Released lease lines are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(line.lease_id.state != "draft" for line in self):
            raise AccessError(_("Released lease lines cannot be deleted."))
        return super().unlink()


class LhiHubLeasePayment(models.Model):
    _name = "lhi.hub.lease.payment"
    _description = "HUB Equipment Lease Payment"
    _order = "payment_date desc, id desc"

    name = fields.Char(
        string="Receipt Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )
    lease_id = fields.Many2one(
        "lhi.hub.equipment.lease", required=True, ondelete="restrict", index=True
    )
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="lease_id.currency_id", store=True)
    payment_method_id = fields.Many2one(
        "lhi.hub.payment.method", required=True, ondelete="restrict"
    )
    payment_reference = fields.Char()
    notes = fields.Text()
    reversal_reason = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")],
        required=True,
        default="draft",
        index=True,
    )
    revenue_entry_id = fields.Many2one(
        "lhi.hub.operational.revenue", readonly=True, ondelete="restrict"
    )
    company_id = fields.Many2one(related="lease_id.company_id", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "draft") != "draft" or vals.get("revenue_entry_id")
            ) and self.env.context.get(
                "lhi_hub_payment_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(_("Payment workflow fields are system-managed."))
            lease = self.env["lhi.hub.equipment.lease"].browse(vals.get("lease_id"))
            if lease.exists():
                lease._lhi_assert_hub_access(lease.hub_id)
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.lease.payment"
                ) or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if (
            any(payment.state != "draft" for payment in self)
            and self.env.context.get("lhi_hub_payment_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            if set(vals).issubset({"reversal_reason"}):
                for payment in self:
                    payment.lease_id._lhi_assert_hub_access(
                        payment.lease_id.hub_id, management=True
                    )
            else:
                raise AccessError(_("Posted lease payments are immutable."))
        if (
            "state" in vals
            and self.env.context.get("lhi_hub_payment_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Use the payment posting workflow."))
        return super().write(vals)

    def unlink(self):
        if any(payment.state != "draft" for payment in self):
            raise AccessError(_("Posted lease payments cannot be deleted."))
        return super().unlink()

    def action_post(self):
        for original in self:
            payment = original.try_lock_for_update()
            if not payment:
                raise UserError(_("This payment is being posted by another user."))
            payment.lease_id._lhi_assert_hub_access(payment.lease_id.hub_id)
            if payment.state != "draft" or payment.amount <= 0:
                raise ValidationError(_("Only a positive draft payment can be posted."))
            if (
                payment.payment_method_id.requires_reference
                and not payment.payment_reference
            ):
                raise ValidationError(_("A payment reference is required."))
            revenue = (
                self.env["lhi.hub.operational.revenue"]
                .with_context(lhi_hub_revenue_system=LHI_HUB_SYSTEM_TOKEN)
                .create(
                    {
                        "name": _("Lease payment %s") % payment.name,
                        "transaction_date": payment.payment_date,
                        "hub_id": payment.lease_id.hub_id.id,
                        "source_model": payment._name,
                        "source_id": payment.id,
                        "source_reference": payment.name,
                        "partner_id": payment.lease_id.lessee_id.id,
                        "officer_id": self.env.user.id,
                        "payment_method_id": payment.payment_method_id.id,
                        "payment_reference": payment.payment_reference,
                        "currency_id": payment.currency_id.id,
                        "amount": payment.amount,
                        "revenue_type": "lease_payment",
                    }
                )
            )
            payment.with_context(lhi_hub_payment_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": "posted", "revenue_entry_id": revenue.id}
            )
        return True

    def action_reverse(self):
        for original in self:
            payment = original.try_lock_for_update()
            if not payment:
                raise UserError(_("This payment is being reversed by another user."))
            payment.lease_id._lhi_assert_hub_access(
                payment.lease_id.hub_id, management=True
            )
            if payment.state != "posted":
                raise ValidationError(_("Only a posted lease payment can be reversed."))
            if not (payment.reversal_reason or "").strip():
                raise ValidationError(_("Record the reversal reason first."))
            self.env["lhi.hub.operational.revenue"].with_context(
                lhi_hub_revenue_system=LHI_HUB_SYSTEM_TOKEN
            ).create(
                {
                    "name": _("Reversal of lease payment %s") % payment.name,
                    "transaction_date": fields.Date.context_today(self),
                    "hub_id": payment.lease_id.hub_id.id,
                    "source_model": payment._name,
                    "source_id": payment.id,
                    "source_reference": payment.name,
                    "partner_id": payment.lease_id.lessee_id.id,
                    "officer_id": self.env.user.id,
                    "payment_method_id": payment.payment_method_id.id,
                    "payment_reference": payment.payment_reference,
                    "currency_id": payment.currency_id.id,
                    "amount": -payment.amount,
                    "revenue_type": "reversal",
                    "reversed_entry_id": payment.revenue_entry_id.id,
                }
            )
            payment.with_context(lhi_hub_payment_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": "reversed"}
            )
        return True
