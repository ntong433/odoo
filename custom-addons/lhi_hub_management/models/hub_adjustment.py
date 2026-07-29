# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class LhiHubStockAdjustment(models.Model):
    _name = "lhi.hub.stock.adjustment"
    _description = "Controlled HUB Stock Adjustment"
    _inherit = ["mail.thread", "mail.activity.mixin", "lhi.hub.access.mixin"]
    _order = "adjustment_date desc, id desc"

    name = fields.Char(
        string="Adjustment Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )
    adjustment_date = fields.Datetime(
        required=True, default=fields.Datetime.now, readonly=True
    )
    hub_id = fields.Many2one(
        "stock.warehouse", required=True, tracking=True, ondelete="restrict"
    )
    location_id = fields.Many2one(
        "stock.location",
        required=True,
        tracking=True,
        ondelete="restrict",
        domain="[('warehouse_id', '=', hub_id), ('usage', '=', 'internal')]",
    )
    reason = fields.Text(
        required=True,
        tracking=True,
        help="Operational reason retained on the inventory movement and audit log.",
    )
    requested_by_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    validated_by_id = fields.Many2one("res.users", readonly=True)
    validated_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many(
        "lhi.hub.stock.adjustment.line", "adjustment_id", copy=True
    )
    reversal_reason = fields.Text()
    reversal_of_id = fields.Many2one(
        "lhi.hub.stock.adjustment", readonly=True, ondelete="restrict"
    )
    reversal_id = fields.Many2one(
        "lhi.hub.stock.adjustment", readonly=True, ondelete="restrict"
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("reversed", "Reversed"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        readonly=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(related="hub_id.company_id", store=True, readonly=True)

    _reversal_unique = models.Constraint(
        "unique(reversal_of_id)",
        "A HUB stock adjustment can be reversed only once.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "draft") != "draft"
                or vals.get("reversal_of_id")
                or vals.get("reversal_id")
                or vals.get("validated_by_id")
                or vals.get("validated_at")
            ) and self.env.context.get(
                "lhi_hub_adjustment_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(
                    _("Stock-adjustment workflow fields are system-managed.")
                )
            hub = self.env["stock.warehouse"].browse(vals.get("hub_id")).exists()
            self._lhi_assert_hub_access(hub, management=True)
            vals["requested_by_id"] = self.env.user.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.stock.adjustment"
                ) or _("New")
        return super().create(vals_list)

    def write(self, vals):
        system_fields = {
            "state",
            "validated_by_id",
            "validated_at",
            "reversal_id",
            "reversal_of_id",
        }
        if (
            system_fields.intersection(vals)
            and self.env.context.get("lhi_hub_adjustment_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Use the controlled stock-adjustment workflow."))
        for adjustment in self:
            adjustment._lhi_assert_hub_access(adjustment.hub_id, management=True)
            if adjustment.state != "draft":
                allowed = {"reversal_reason"} | system_fields
                if not set(vals).issubset(allowed):
                    raise AccessError(_("Validated stock adjustments are immutable."))
        return super().write(vals)

    def unlink(self):
        for adjustment in self:
            adjustment._lhi_assert_hub_access(adjustment.hub_id, management=True)
            if adjustment.state != "draft":
                raise AccessError(_("Validated stock adjustments cannot be deleted."))
        return super().unlink()

    @api.constrains("hub_id", "location_id")
    def _check_location(self):
        for adjustment in self:
            if (
                adjustment.location_id
                and adjustment.location_id.warehouse_id != adjustment.hub_id
            ):
                raise ValidationError(
                    _("The storage location must belong to the selected HUB.")
                )

    def _lhi_inventory_loss_location(self, product):
        self.ensure_one()
        company = self.company_id
        location = product.with_company(company).property_stock_inventory
        if not location:
            location_id = (
                self.env["ir.default"]
                .with_company(company)
                ._get_model_defaults("product.template")
                .get("property_stock_inventory")
            )
            location = self.env["stock.location"].browse(location_id).exists()
        if not location:
            raise ValidationError(
                _("Configure an inventory-loss location before validating.")
            )
        return location

    def action_validate(self):
        move_model = self.env["stock.move"]
        quant_model = self.env["stock.quant"]
        for original in self:
            adjustment = original.try_lock_for_update()
            if not adjustment:
                raise UserError(
                    _("This stock adjustment is being processed by another user.")
                )
            adjustment._lhi_assert_hub_access(adjustment.hub_id, management=True)
            if adjustment.state != "draft":
                raise UserError(_("Only a draft stock adjustment can be validated."))
            if not (adjustment.reason or "").strip():
                raise ValidationError(_("A stock-adjustment reason is required."))
            if not adjustment.line_ids:
                raise ValidationError(_("Add at least one adjustment line."))

            for line in adjustment.line_ids:
                line._lhi_validate()
                # Serialize inventory deltas by company/location/product/lot.
                # PostgreSQL releases this parameterized transaction lock
                # automatically; no persistent technical lock rows are needed.
                lock_key = "%s:%s:%s:%s" % (
                    adjustment.company_id.id,
                    adjustment.location_id.id,
                    line.product_id.id,
                    line.lot_id.id or 0,
                )
                self.env.cr.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    [lock_key],
                )
                base_quantity = line.uom_id._compute_quantity(
                    line.adjustment_quantity, line.product_id.uom_id
                )
                before = quant_model._get_available_quantity(
                    line.product_id,
                    adjustment.location_id,
                    lot_id=line.lot_id,
                    strict=True,
                )
                if base_quantity < 0 and (
                    before + base_quantity < -line.product_id.uom_id.rounding
                ):
                    raise ValidationError(
                        _("Adjustment would make %(product)s negative at %(location)s.")
                        % {
                            "product": line.product_id.display_name,
                            "location": adjustment.location_id.display_name,
                        }
                    )
                inventory_location = adjustment._lhi_inventory_loss_location(
                    line.product_id
                )
                if base_quantity > 0:
                    source, destination = (
                        inventory_location,
                        adjustment.location_id,
                    )
                else:
                    source, destination = (
                        adjustment.location_id,
                        inventory_location,
                    )
                quantity = abs(base_quantity)
                move = move_model.with_context(
                    lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN
                ).create(
                    {
                        "name": line.product_id.display_name,
                        "inventory_name": _("%(reference)s — %(reason)s")
                        % {
                            "reference": adjustment.name,
                            "reason": adjustment.reason.strip(),
                        },
                        "origin": adjustment.name,
                        "product_id": line.product_id.id,
                        "product_uom": line.product_id.uom_id.id,
                        "product_uom_qty": quantity,
                        "company_id": adjustment.company_id.id,
                        "location_id": source.id,
                        "location_dest_id": destination.id,
                        "state": "confirmed",
                        "is_inventory": True,
                        "picked": True,
                        "lhi_stock_adjustment_line_id": line.id,
                        "move_line_ids": [
                            (
                                0,
                                0,
                                {
                                    "product_id": line.product_id.id,
                                    "product_uom_id": line.product_id.uom_id.id,
                                    "quantity": quantity,
                                    "location_id": source.id,
                                    "location_dest_id": destination.id,
                                    "company_id": adjustment.company_id.id,
                                    "lot_id": line.lot_id.id,
                                    "picked": True,
                                },
                            )
                        ],
                    }
                )
                move._action_done()
                after = quant_model._get_available_quantity(
                    line.product_id,
                    adjustment.location_id,
                    lot_id=line.lot_id,
                    strict=True,
                )
                line.with_context(lhi_hub_adjustment_system=LHI_HUB_SYSTEM_TOKEN).write(
                    {
                        "quantity_before": before,
                        "quantity_after": after,
                        "move_id": move.id,
                    }
                )

            adjustment.with_context(
                lhi_hub_adjustment_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "state": "validated",
                    "validated_by_id": self.env.user.id,
                    "validated_at": fields.Datetime.now(),
                }
            )
            self.env["lhi.audit.log"].create_event(
                event_type="hub_operation",
                res_model=adjustment._name,
                res_id=adjustment.id,
                description=_("Validated controlled stock adjustment %s.")
                % adjustment.name,
            )
        return True

    def action_reverse(self):
        for adjustment in self:
            adjustment._lhi_assert_hub_access(adjustment.hub_id, management=True)
            if adjustment.state != "validated" or adjustment.reversal_id:
                raise UserError(
                    _("Only an unreversed validated adjustment can be reversed.")
                )
            if not (adjustment.reversal_reason or "").strip():
                raise ValidationError(_("A reversal reason is required."))
            reversal = self.with_context(
                lhi_hub_adjustment_system=LHI_HUB_SYSTEM_TOKEN
            ).create(
                {
                    "hub_id": adjustment.hub_id.id,
                    "location_id": adjustment.location_id.id,
                    "reason": _("Reversal of %(reference)s: %(reason)s")
                    % {
                        "reference": adjustment.name,
                        "reason": adjustment.reversal_reason.strip(),
                    },
                    "reversal_of_id": adjustment.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "uom_id": line.uom_id.id,
                                "lot_id": line.lot_id.id,
                                "adjustment_quantity": -line.adjustment_quantity,
                            },
                        )
                        for line in adjustment.line_ids
                    ],
                }
            )
            reversal.action_validate()
            adjustment.with_context(
                lhi_hub_adjustment_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"state": "reversed", "reversal_id": reversal.id})
        return True


class LhiHubStockAdjustmentLine(models.Model):
    _name = "lhi.hub.stock.adjustment.line"
    _description = "Controlled HUB Stock Adjustment Line"
    _order = "id"

    adjustment_id = fields.Many2one(
        "lhi.hub.stock.adjustment", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
        domain="[('is_storable', '=', True), ('lhi_hub_item_type', '!=', False)]",
    )
    uom_id = fields.Many2one("uom.uom", required=True)
    lot_id = fields.Many2one(
        "stock.lot",
        ondelete="restrict",
        domain="[('product_id', '=', product_id), ('company_id', 'in', [False, company_id])]",
    )
    adjustment_quantity = fields.Float(
        required=True,
        digits="Product Unit of Measure",
        help="Positive adds stock; negative removes stock.",
    )
    quantity_before = fields.Float(readonly=True, digits="Product Unit of Measure")
    quantity_after = fields.Float(readonly=True, digits="Product Unit of Measure")
    move_id = fields.Many2one("stock.move", readonly=True, ondelete="restrict")
    company_id = fields.Many2one(
        related="adjustment_id.company_id", store=True, readonly=True
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    def _lhi_validate(self):
        self.ensure_one()
        if self.product_id.uom_id.compare(self.adjustment_quantity, 0) == 0:
            raise ValidationError(_("Adjustment quantity cannot be zero."))
        if self.uom_id.category_id != self.product_id.uom_id.category_id:
            raise ValidationError(_("Use a unit of measure in the product category."))
        if self.product_id.tracking != "none" and not self.lot_id:
            raise ValidationError(
                _("Select a lot or serial for %s.") % self.product_id.display_name
            )
        base_quantity = self.uom_id._compute_quantity(
            self.adjustment_quantity, self.product_id.uom_id
        )
        if self.product_id.tracking == "serial" and not self.product_id.uom_id.is_zero(
            abs(base_quantity) - 1
        ):
            raise ValidationError(
                _("A serial-number adjustment must add or remove exactly one unit.")
            )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if {"quantity_before", "quantity_after", "move_id"}.intersection(
                vals
            ) and self.env.context.get(
                "lhi_hub_adjustment_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(_("Adjustment results are workflow-managed."))
            adjustment = self.env["lhi.hub.stock.adjustment"].browse(
                vals.get("adjustment_id")
            )
            if adjustment.exists():
                adjustment._lhi_assert_hub_access(adjustment.hub_id, management=True)
                if adjustment.state != "draft":
                    raise AccessError(
                        _("Lines can be added only to draft adjustments.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        if {"quantity_before", "quantity_after", "move_id"}.intersection(
            vals
        ) and self.env.context.get(
            "lhi_hub_adjustment_system"
        ) is not LHI_HUB_SYSTEM_TOKEN:
            raise AccessError(_("Adjustment results are workflow-managed."))
        for line in self:
            line.adjustment_id._lhi_assert_hub_access(
                line.adjustment_id.hub_id, management=True
            )
            if (
                line.adjustment_id.state != "draft"
                and self.env.context.get("lhi_hub_adjustment_system")
                is not LHI_HUB_SYSTEM_TOKEN
            ):
                raise AccessError(_("Validated adjustment lines are immutable."))
        return super().write(vals)

    def unlink(self):
        for line in self:
            line.adjustment_id._lhi_assert_hub_access(
                line.adjustment_id.hub_id, management=True
            )
            if line.adjustment_id.state != "draft":
                raise AccessError(_("Validated adjustment lines cannot be deleted."))
        return super().unlink()
