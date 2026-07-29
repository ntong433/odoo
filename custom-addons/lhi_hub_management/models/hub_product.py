# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


class ProductCategory(models.Model):
    _inherit = "product.category"

    lhi_hub_category_code = fields.Selection(
        [
            ("nfi", "NFI – Non-Food Items"),
            ("medical", "Medical Equipment"),
            ("consumables", "Consumables"),
            ("pharmaceuticals", "Pharmaceuticals"),
        ],
        string="LHI HUB Top-level Category",
        index=True,
    )
    lhi_protected_hub_category = fields.Boolean(readonly=True, copy=False)

    @api.constrains("lhi_hub_category_code", "parent_id")
    def _check_lhi_top_level_category(self):
        for category in self:
            if category.lhi_hub_category_code and category.parent_id:
                raise ValidationError(
                    _("Protected LHI HUB categories must remain top-level categories.")
                )

    def write(self, vals):
        protected_fields = {"name", "parent_id", "lhi_hub_category_code", "active"}
        if protected_fields.intersection(vals):
            protected = self.filtered("lhi_protected_hub_category")
            if protected and not self.env.user.has_group(
                "lhi_security.group_lhi_erp_admin"
            ):
                raise AccessError(
                    _(
                        "Only LHI ERP Administrators may change protected HUB categories."
                    )
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered("lhi_protected_hub_category"):
            raise ValidationError(
                _("Protected LHI HUB top-level categories cannot be deleted.")
            )
        return super().unlink()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    lhi_hub_item_type = fields.Selection(
        [
            ("nfi", "NFI – Non-Food Items"),
            ("medical", "Medical Equipment"),
            ("consumables", "Consumables"),
            ("pharmaceuticals", "Pharmaceuticals"),
        ],
        string="HUB Item Category",
        index=True,
    )
    lhi_controlled_item = fields.Boolean()
    lhi_leaseable = fields.Boolean(string="Leaseable Equipment")
    lhi_individually_identifiable = fields.Boolean(
        string="Individually Identifiable Equipment"
    )
    lhi_asset_category_id = fields.Many2one(
        "lhi.asset.category", string="Asset Category when Promoted"
    )
    lhi_low_stock_threshold = fields.Float(default=0.0)
    lhi_lease_daily_rate = fields.Monetary(
        string="Default Daily Lease Rate",
        currency_field="lhi_value_currency_id",
        default=0.0,
    )
    lhi_temperature_requirement = fields.Char()
    lhi_value_source = fields.Selection(
        [
            ("purchase_price", "Purchase Price"),
            ("donor_declared", "Donor-declared Value"),
            ("partner_declared", "Partner-declared Value"),
            ("replacement", "Estimated Replacement Value"),
            ("legacy", "Imported Legacy Value"),
            ("manual", "Approved Manual Valuation"),
        ],
        string="Operational Value Source",
    )
    lhi_purchase_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_donor_declared_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_partner_declared_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_replacement_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_legacy_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_manual_value = fields.Monetary(currency_field="lhi_value_currency_id")
    lhi_operational_unit_value = fields.Monetary(
        string="Operational Unit Value",
        currency_field="lhi_value_currency_id",
        compute="_compute_lhi_operational_unit_value",
        store=True,
    )
    lhi_value_currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    lhi_value_date = fields.Date()

    @api.depends(
        "lhi_value_source",
        "lhi_purchase_value",
        "lhi_donor_declared_value",
        "lhi_partner_declared_value",
        "lhi_replacement_value",
        "lhi_legacy_value",
        "lhi_manual_value",
    )
    def _compute_lhi_operational_unit_value(self):
        field_by_source = {
            "purchase_price": "lhi_purchase_value",
            "donor_declared": "lhi_donor_declared_value",
            "partner_declared": "lhi_partner_declared_value",
            "replacement": "lhi_replacement_value",
            "legacy": "lhi_legacy_value",
            "manual": "lhi_manual_value",
        }
        for product in self:
            field_name = field_by_source.get(product.lhi_value_source)
            product.lhi_operational_unit_value = (
                product[field_name] if field_name else 0.0
            )

    @api.constrains(
        "lhi_hub_item_type",
        "tracking",
        "use_expiration_date",
        "is_storable",
        "lhi_individually_identifiable",
        "lhi_leaseable",
    )
    def _check_lhi_tracking_policy(self):
        for product in self:
            if not product.lhi_hub_item_type:
                continue
            if not product.is_storable:
                raise ValidationError(_("HUB items must track inventory."))
            if product.lhi_hub_item_type == "pharmaceuticals":
                if product.tracking == "none" or not product.use_expiration_date:
                    raise ValidationError(
                        _(
                            "Pharmaceuticals require lot/batch tracking and "
                            "expiration dates."
                        )
                    )
            if (
                product.lhi_individually_identifiable or product.lhi_leaseable
            ) and product.tracking != "serial":
                raise ValidationError(
                    _(
                        "Individually identifiable or leaseable equipment requires serial tracking."
                    )
                )


class StockLot(models.Model):
    _inherit = "stock.lot"

    lhi_hub_id = fields.Many2one(
        "stock.warehouse",
        string="Controlling HUB",
        ondelete="restrict",
        index=True,
        help="Operational HUB scope retained while stock is issued or in transit.",
    )
    lhi_manufacturing_date = fields.Date()
    lhi_donor_id = fields.Many2one("res.partner", string="Donor or Partner")
    lhi_consignment_id = fields.Many2one(
        "lhi.hub.consignment", string="Consignment", ondelete="restrict"
    )
    lhi_project_id = fields.Many2one("lhi.project")
    lhi_award_id = fields.Many2one("lhi.award", string="Grant or Award")
    lhi_quarantine_status = fields.Selection(
        [
            ("released", "Released"),
            ("quarantined", "Quarantined"),
            ("rejected", "Rejected"),
        ],
        default="released",
        required=True,
        index=True,
        tracking=True,
    )
    lhi_quarantine_reason = fields.Text()
    lhi_temperature_requirement = fields.Char()
    lhi_asset_id = fields.Many2one(
        "lhi.asset", string="Linked Asset Register Record", ondelete="restrict"
    )

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any("lhi_hub_id" in vals for vals in vals_list)
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Lot/serial HUB provenance is workflow-managed."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            "lhi_hub_id" in vals
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("Lot/serial HUB provenance is workflow-managed."))
        return super().write(vals)

    @api.constrains(
        "lhi_manufacturing_date",
        "expiration_date",
        "removal_date",
        "lhi_quarantine_status",
        "lhi_quarantine_reason",
    )
    def _check_lhi_lot_dates(self):
        for lot in self:
            expiry = fields.Date.to_date(lot.expiration_date)
            removal = fields.Date.to_date(lot.removal_date)
            if (
                lot.lhi_manufacturing_date
                and expiry
                and lot.lhi_manufacturing_date > expiry
            ):
                raise ValidationError(
                    _("Manufacturing date cannot be after the expiry date.")
                )
            if removal and expiry and removal > expiry:
                raise ValidationError(_("Removal date cannot be after expiry date."))
            if (
                lot.lhi_quarantine_status != "released"
                and not (lot.lhi_quarantine_reason or "").strip()
            ):
                raise ValidationError(
                    _("A quarantine or rejection reason is required.")
                )

    def _lhi_assert_issuable(self, on_date=None):
        on_date = on_date or fields.Date.context_today(self)
        for lot in self:
            if lot.lhi_quarantine_status != "released":
                raise ValidationError(
                    _("Lot/serial %s is quarantined or rejected.") % lot.display_name
                )
            expiry = fields.Date.to_date(lot.expiration_date)
            removal = fields.Date.to_date(lot.removal_date)
            if (expiry and expiry <= on_date) or (removal and removal <= on_date):
                raise ValidationError(
                    _("Expired or removal-date stock (%s) cannot be issued.")
                    % lot.display_name
                )
        return True

    def action_promote_to_asset_register(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_officer"):
            raise AccessError(
                _("Only Asset Officers may promote serialised equipment.")
            )
        condition = self.env.ref(
            "lhi_asset_management.asset_condition_good", raise_if_not_found=False
        )
        for lot in self:
            if lot.lhi_asset_id:
                continue
            template = lot.product_id.product_tmpl_id
            if (
                lot.product_id.tracking != "serial"
                or not template.lhi_asset_category_id
            ):
                raise ValidationError(
                    _(
                        "Serial tracking and an Asset Category mapping are "
                        "required before promotion."
                    )
                )
            hub = lot.location_id.warehouse_id
            asset = self.env["lhi.asset"].create(
                {
                    "name": lot.product_id.display_name,
                    "serial_number": lot.name,
                    "category_id": template.lhi_asset_category_id.id,
                    "condition_id": condition.id,
                    "acquisition_type": "donated" if lot.lhi_donor_id else "purchased",
                    "legal_owner_id": lot.company_id.partner_id.id,
                    "donor_id": lot.lhi_donor_id.id,
                    "project_id": lot.lhi_project_id.id,
                    "award_id": lot.lhi_award_id.id,
                    "registration_state_id": hub.lhi_state_id.id,
                    "state_id": hub.lhi_state_id.id,
                    "office_id": hub.lhi_office_id.id,
                    "hub_id": hub.id,
                    "currency_id": template.lhi_value_currency_id.id,
                    "asset_value": template.lhi_operational_unit_value,
                    "value_source": template.lhi_value_source,
                    "value_date": template.lhi_value_date,
                    "company_id": lot.company_id.id,
                    "stock_lot_id": lot.id,
                }
            )
            asset.action_confirm()
            lot.lhi_asset_id = asset.id
        return True


class LhiAsset(models.Model):
    _inherit = "lhi.asset"

    stock_lot_id = fields.Many2one(
        "stock.lot", string="Related HUB Lot / Serial", ondelete="restrict"
    )


class StockQuant(models.Model):
    _inherit = "stock.quant"

    lhi_operational_stock_value = fields.Monetary(
        compute="_compute_lhi_operational_stock_value",
        currency_field="lhi_value_currency_id",
    )
    lhi_value_currency_id = fields.Many2one(related="product_id.lhi_value_currency_id")

    @api.depends("quantity", "product_id.lhi_operational_unit_value")
    def _compute_lhi_operational_stock_value(self):
        for quant in self:
            quant.lhi_operational_stock_value = (
                quant.quantity * quant.product_id.lhi_operational_unit_value
            )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    lhi_hub_request_id = fields.Many2one(
        "lhi.hub.stock.request", ondelete="restrict", index=True
    )
    lhi_consignment_id = fields.Many2one(
        "lhi.hub.consignment", ondelete="restrict", index=True
    )
    lhi_external_issue_id = fields.Many2one(
        "lhi.hub.external.issue", ondelete="restrict", index=True
    )
    lhi_equipment_lease_id = fields.Many2one(
        "lhi.hub.equipment.lease", ondelete="restrict", index=True
    )
    lhi_hub_document_type = fields.Selection(
        [
            ("request_dispatch", "HUB Request Dispatch"),
            ("request_receipt", "HUB Request Receipt"),
            ("consignment", "Consignment Receipt"),
            ("external_issue", "External Issue"),
            ("lease_release", "Lease Release"),
            ("lease_return", "Lease Return"),
            ("reversal", "Reversal"),
        ],
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        provenance = {
            "lhi_hub_request_id",
            "lhi_consignment_id",
            "lhi_external_issue_id",
            "lhi_equipment_lease_id",
            "lhi_hub_document_type",
        }
        if (
            any(provenance.intersection(vals) for vals in vals_list)
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB stock provenance is workflow-generated."))
        return super().create(vals_list)

    def write(self, vals):
        provenance = {
            "lhi_hub_request_id",
            "lhi_consignment_id",
            "lhi_external_issue_id",
            "lhi_equipment_lease_id",
            "lhi_hub_document_type",
        }
        if (
            provenance.intersection(vals)
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB stock provenance is immutable."))
        return super().write(vals)


class StockMove(models.Model):
    _inherit = "stock.move"

    lhi_hub_request_line_id = fields.Many2one(
        "lhi.hub.stock.request.line", ondelete="restrict", index=True
    )
    lhi_consignment_line_id = fields.Many2one(
        "lhi.hub.consignment.line", ondelete="restrict", index=True
    )
    lhi_external_issue_line_id = fields.Many2one(
        "lhi.hub.external.issue.line", ondelete="restrict", index=True
    )
    lhi_lease_line_id = fields.Many2one(
        "lhi.hub.equipment.lease.line", ondelete="restrict", index=True
    )
    lhi_stock_adjustment_line_id = fields.Many2one(
        "lhi.hub.stock.adjustment.line", ondelete="restrict", index=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        provenance = {
            "lhi_hub_request_line_id",
            "lhi_consignment_line_id",
            "lhi_external_issue_line_id",
            "lhi_lease_line_id",
            "lhi_stock_adjustment_line_id",
        }
        if (
            any(provenance.intersection(vals) for vals in vals_list)
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB stock-move provenance is workflow-generated."))
        return super().create(vals_list)

    def write(self, vals):
        provenance = {
            "lhi_hub_request_line_id",
            "lhi_consignment_line_id",
            "lhi_external_issue_line_id",
            "lhi_lease_line_id",
            "lhi_stock_adjustment_line_id",
        }
        if (
            provenance.intersection(vals)
            and self.env.context.get("lhi_hub_stock_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB stock-move provenance is immutable."))
        return super().write(vals)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.constrains("lot_id", "location_id", "location_dest_id", "quantity")
    def _check_lhi_expired_or_quarantined_issue(self):
        for line in self.filtered(
            lambda item: (
                item.lot_id
                and item.quantity > 0
                and item.location_id.usage == "internal"
                and item.location_dest_id.usage in ("customer", "transit")
            )
        ):
            line.lot_id._lhi_assert_issuable()
