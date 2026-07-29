# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class LhiHubConsignment(models.Model):
    _name = "lhi.hub.consignment"
    _description = "LHI HUB Donor or Partner Consignment"
    _inherit = ["mail.thread", "mail.activity.mixin", "lhi.hub.access.mixin"]
    _order = "delivery_date desc, id desc"

    name = fields.Char(
        string="Consignment Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )
    partner_id = fields.Many2one(
        "res.partner", string="Donor or Partner", required=True, tracking=True
    )
    funding_agreement = fields.Char()
    project_id = fields.Many2one("lhi.project")
    programme_id = fields.Many2one("lhi.programme")
    award_id = fields.Many2one("lhi.award", string="Grant or Award")
    hub_id = fields.Many2one(
        "stock.warehouse", string="Destination HUB", required=True, tracking=True
    )
    delivery_date = fields.Date(required=True, default=fields.Date.context_today)
    waybill = fields.Char()
    donor_reference = fields.Char()
    line_ids = fields.One2many("lhi.hub.consignment.line", "consignment_id", copy=True)
    ownership_status = fields.Selection(
        [
            ("lhi_owned", "LHI-owned"),
            ("donor_owned", "Donor-owned"),
            ("restricted_use", "Restricted Use"),
            ("pending", "Ownership Pending"),
        ],
        default="pending",
        required=True,
    )
    usage_restrictions = fields.Text()
    supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_hub_consignment_attachment_rel",
        "consignment_id",
        "attachment_id",
    )
    received_by_id = fields.Many2one("res.users", readonly=True)
    inspection_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("passed", "Passed"),
            ("discrepancy", "Discrepancies Recorded"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    discrepancies = fields.Text()
    approval_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="not_required",
        required=True,
    )
    notes = fields.Html()
    picking_id = fields.Many2one("stock.picking", readonly=True, ondelete="restrict")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("expected", "Expected at HUB"),
            ("received", "Physically Received"),
            ("inspected", "Inspected"),
            ("discrepancy", "Discrepancies Recorded"),
            ("posted", "Accepted Stock Posted"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(related="hub_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    total_declared_value = fields.Monetary(
        compute="_compute_total_declared_value", store=True
    )

    _partner_reference_unique = models.Constraint(
        "unique(partner_id, donor_reference, company_id)",
        "This donor/partner reference already exists for the company.",
    )

    @api.depends("line_ids.total_declared_value")
    def _compute_total_declared_value(self):
        for consignment in self:
            consignment.total_declared_value = sum(
                consignment.line_ids.mapped("total_declared_value")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "draft") != "draft"
                or vals.get("picking_id")
                or vals.get("received_by_id")
            ) and self.env.context.get(
                "lhi_hub_consignment_system"
            ) is not LHI_HUB_SYSTEM_TOKEN:
                raise AccessError(_("Consignment workflow fields are system-managed."))
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.consignment"
                ) or _("New")
        return super().create(vals_list)

    def write(self, vals):
        material = {
            "partner_id",
            "project_id",
            "programme_id",
            "award_id",
            "hub_id",
            "delivery_date",
            "line_ids",
            "ownership_status",
            "usage_restrictions",
        }
        if material.intersection(vals) and any(
            record.state not in ("draft", "submitted", "expected", "received")
            for record in self
        ):
            raise ValidationError(_("Inspected consignments are immutable."))
        if (
            "state" in vals
            and self.env.context.get("lhi_hub_consignment_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(
                _("Use the consignment workflow actions to change status.")
            )
        return super().write(vals)

    def action_submit(self):
        for consignment in self:
            consignment._lhi_assert_hub_access(consignment.hub_id)
            if not consignment.line_ids:
                raise ValidationError(_("Add at least one consignment line."))
            consignment.with_context(
                lhi_hub_consignment_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"state": "submitted"})
        return True

    def action_mark_expected(self):
        self._transition("submitted", "expected")
        return True

    def action_mark_received(self):
        for consignment in self:
            consignment._lhi_assert_hub_access(consignment.hub_id)
            if consignment.state != "expected":
                raise UserError(_("Only expected consignments can be received."))
            if any(line.received_quantity < 0 for line in consignment.line_ids):
                raise ValidationError(_("Received quantities cannot be negative."))
            consignment.with_context(
                lhi_hub_consignment_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "state": "received",
                    "received_by_id": self.env.user.id,
                }
            )
        return True

    def action_inspect(self):
        for consignment in self:
            consignment._lhi_assert_hub_access(consignment.hub_id)
            if consignment.state != "received":
                raise UserError(
                    _("Only physically received consignments can be inspected.")
                )
            for line in consignment.line_ids:
                if (
                    line.accepted_quantity + line.rejected_quantity
                    > line.received_quantity
                ):
                    raise ValidationError(
                        _("Accepted plus rejected quantity exceeds received quantity.")
                    )
                line._lhi_validate_pharmaceutical_data()
            has_discrepancy = any(
                line.received_quantity != line.expected_quantity
                or line.rejected_quantity
                for line in consignment.line_ids
            )
            consignment.with_context(
                lhi_hub_consignment_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "state": "discrepancy" if has_discrepancy else "inspected",
                    "inspection_status": (
                        "discrepancy" if has_discrepancy else "passed"
                    ),
                }
            )
            if has_discrepancy:
                self.env["lhi.hub.notification"].enqueue(
                    source=consignment,
                    event_type="consignment_discrepancy",
                    message=_(
                        "Consignment %s has quantity or inspection discrepancies."
                    )
                    % consignment.name,
                    users=consignment.hub_id.lhi_operations_manager_id
                    | consignment.hub_id.lhi_warehouse_officer_ids
                    | consignment.hub_id.lhi_operations_officer_ids,
                )
        return True

    def action_post_accepted_stock(self):
        stock_service = self.env["lhi.hub.stock.service"]
        supplier_location = self.env.ref("stock.stock_location_suppliers")
        for consignment in self:
            consignment._lhi_assert_hub_access(consignment.hub_id)
            if consignment.state not in ("inspected", "discrepancy"):
                raise UserError(
                    _("Inspect the consignment before posting accepted stock.")
                )
            if consignment.picking_id:
                raise ValidationError(_("Accepted stock has already been posted."))
            destination = (
                consignment.hub_id.lhi_default_receipt_location_id
                or consignment.hub_id.lot_stock_id
            )
            specs = []
            for line in consignment.line_ids.filtered(
                lambda item: item.accepted_quantity > 0
            ):
                lot = line._lhi_resolve_or_create_lot()
                specs.append(
                    {
                        "product": line.product_id,
                        "quantity": line.accepted_quantity,
                        "uom": line.uom_id,
                        "lot": lot,
                        "values": {
                            "lhi_consignment_line_id": line.id,
                            "lhi_project_id": consignment.project_id.id,
                            "lhi_donor_id": consignment.partner_id.id,
                        },
                    }
                )
            picking = stock_service._lhi_create_picking(
                picking_type=consignment.hub_id.in_type_id,
                source_location=supplier_location,
                destination_location=destination,
                origin=consignment.name,
                move_specs=specs,
                picking_values={
                    "lhi_consignment_id": consignment.id,
                    "lhi_hub_document_type": "consignment",
                    "lhi_project_id": consignment.project_id.id,
                    "lhi_donor_id": consignment.partner_id.id,
                },
            )
            for move in picking.move_ids.filtered(
                lambda item: item.product_id.tracking != "none"
            ):
                lot = move.lhi_consignment_line_id.lot_id
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": move.product_uom_qty,
                        "lot_id": lot.id,
                        "location_id": supplier_location.id,
                        "location_dest_id": destination.id,
                        "company_id": consignment.company_id.id,
                    }
                )
            stock_service._lhi_validate_picking(picking)
            consignment.with_context(
                lhi_hub_consignment_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"picking_id": picking.id, "state": "posted"})
            consignment.message_post(
                body=_("Accepted stock posted through validated receipt %s.")
                % picking.name
            )
        return True

    def action_close(self):
        self._transition("posted", "closed")
        return True

    def _transition(self, source, destination):
        for consignment in self:
            consignment._lhi_assert_hub_access(consignment.hub_id)
            if consignment.state != source:
                raise UserError(
                    _("Expected status %(source)s before %(destination)s.")
                    % {"source": source, "destination": destination}
                )
            consignment.with_context(
                lhi_hub_consignment_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"state": destination})

    def unlink(self):
        if any(record.state != "draft" for record in self):
            raise ValidationError(_("Submitted consignments cannot be deleted."))
        return super().unlink()


class LhiHubConsignmentLine(models.Model):
    _name = "lhi.hub.consignment.line"
    _description = "LHI HUB Consignment Line"
    _order = "id"

    consignment_id = fields.Many2one(
        "lhi.hub.consignment", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain="[('is_storable', '=', True), ('lhi_hub_item_type', '!=', False)]",
    )
    uom_id = fields.Many2one(
        "uom.uom", required=True, default=lambda self: self.product_id.uom_id
    )
    expected_quantity = fields.Float(required=True)
    received_quantity = fields.Float()
    accepted_quantity = fields.Float()
    rejected_quantity = fields.Float()
    unit_operational_value = fields.Monetary(
        required=True, currency_field="currency_id"
    )
    total_declared_value = fields.Monetary(
        compute="_compute_total", store=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(related="consignment_id.currency_id", store=True)
    company_id = fields.Many2one(
        related="consignment_id.company_id", store=True, readonly=True
    )
    lot_id = fields.Many2one("stock.lot", ondelete="restrict")
    batch_or_serial_number = fields.Char()
    manufacturing_date = fields.Date()
    expiry_date = fields.Datetime()
    removal_date = fields.Datetime()
    discrepancy_notes = fields.Text()

    @api.depends("accepted_quantity", "unit_operational_value")
    def _compute_total(self):
        for line in self:
            line.total_declared_value = (
                line.accepted_quantity * line.unit_operational_value
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_operational_value = self.product_id.lhi_operational_unit_value

    @api.constrains(
        "expected_quantity",
        "received_quantity",
        "accepted_quantity",
        "rejected_quantity",
    )
    def _check_quantities(self):
        for line in self:
            if (
                min(
                    line.expected_quantity,
                    line.received_quantity,
                    line.accepted_quantity,
                    line.rejected_quantity,
                )
                < 0
            ):
                raise ValidationError(_("Consignment quantities cannot be negative."))
            if line.expected_quantity <= 0:
                raise ValidationError(_("Expected quantity must be positive."))
            if line.accepted_quantity + line.rejected_quantity > line.received_quantity:
                raise ValidationError(
                    _(
                        "Accepted plus rejected quantity cannot exceed received quantity."
                    )
                )

    def _lhi_validate_pharmaceutical_data(self):
        self.ensure_one()
        if self.product_id.lhi_hub_item_type != "pharmaceuticals":
            return True
        if not self.batch_or_serial_number or not self.expiry_date:
            raise ValidationError(
                _("Pharmaceutical lines require a batch number and expiry date.")
            )
        if fields.Datetime.to_datetime(self.expiry_date) <= fields.Datetime.now():
            raise ValidationError(_("Expired pharmaceuticals cannot be accepted."))
        return True

    def _lhi_resolve_or_create_lot(self):
        self.ensure_one()
        if self.product_id.tracking == "none":
            return self.env["stock.lot"]
        self._lhi_validate_pharmaceutical_data()
        lot = self.lot_id
        if not lot:
            if not self.batch_or_serial_number:
                raise ValidationError(
                    _("A batch or serial number is required for tracked stock.")
                )
            lot = self.env["stock.lot"].search(
                [
                    ("product_id", "=", self.product_id.id),
                    ("name", "=", self.batch_or_serial_number),
                    ("company_id", "in", [False, self.consignment_id.company_id.id]),
                ],
                limit=1,
            )
        values = {
            "lhi_hub_id": self.consignment_id.hub_id.id,
            "lhi_manufacturing_date": self.manufacturing_date,
            "expiration_date": self.expiry_date,
            "removal_date": self.removal_date,
            "lhi_donor_id": self.consignment_id.partner_id.id,
            "lhi_consignment_id": self.consignment_id.id,
            "lhi_project_id": self.consignment_id.project_id.id,
            "lhi_award_id": self.consignment_id.award_id.id,
            "lhi_quarantine_status": "released",
        }
        if not lot:
            values.update(
                {
                    "name": self.batch_or_serial_number,
                    "product_id": self.product_id.id,
                    "company_id": self.consignment_id.company_id.id,
                }
            )
            lot = (
                self.env["stock.lot"]
                .with_context(lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN)
                .create(values)
            )
        else:
            lot.with_context(lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN).write(
                {key: value for key, value in values.items() if value}
            )
        self.lot_id = lot.id
        return lot

    def write(self, vals):
        if any(line.consignment_id.state in ("posted", "closed") for line in self):
            raise ValidationError(_("Posted consignment lines are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(line.consignment_id.state != "draft" for line in self):
            raise ValidationError(_("Submitted consignment lines cannot be deleted."))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            consignment = self.env["lhi.hub.consignment"].browse(
                vals.get("consignment_id")
            )
            if consignment.exists():
                consignment._lhi_assert_hub_access(consignment.hub_id)
                if consignment.state != "draft":
                    raise AccessError(
                        _("Lines can be added only to draft consignments.")
                    )
        return super().create(vals_list)
