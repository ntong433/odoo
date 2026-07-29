# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


HUB_EXECUTION_GROUPS = (
    "lhi_security.group_lhi_warehouse_officer",
    "lhi_security.group_lhi_operations_officer",
    "lhi_security.group_lhi_operations_manager",
    "lhi_security.group_lhi_director_operations",
)
HUB_MANAGEMENT_GROUPS = (
    "lhi_security.group_lhi_operations_manager",
    "lhi_security.group_lhi_director_operations",
    "lhi_security.group_lhi_erp_admin",
    "lhi_security.group_lhi_system_auditor",
)

# Never use a truthy context flag as a workflow authorization boundary: RPC
# callers control their context.  This process-local object survives internal
# ``with_context`` copies but cannot be reproduced by a JSON/RPC client.
LHI_HUB_SYSTEM_TOKEN = object()


class LhiAuditLog(models.Model):
    _inherit = "lhi.audit.log"

    event_type = fields.Selection(
        selection_add=[("hub_operation", "HUB Operational Event")],
        ondelete={"hub_operation": "cascade"},
    )


class ResUsers(models.Model):
    _inherit = "res.users"

    lhi_hub_ids = fields.Many2many(
        "stock.warehouse",
        "lhi_hub_authorized_user_rel",
        "user_id",
        "warehouse_id",
        string="Authorized HUBs",
        help="HUBs the user may view or transact against, subject to their role.",
    )


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    lhi_state_id = fields.Many2one("res.country.state", string="State")
    lhi_office_id = fields.Many2one("lhi.office", string="Office")
    lhi_operations_manager_id = fields.Many2one(
        "res.users", string="Operations Manager"
    )
    lhi_warehouse_officer_ids = fields.Many2many(
        "res.users",
        "lhi_hub_warehouse_officer_rel",
        "warehouse_id",
        "user_id",
        string="Assigned Warehouse Officers",
    )
    lhi_operations_officer_ids = fields.Many2many(
        "res.users",
        "lhi_hub_operations_officer_rel",
        "warehouse_id",
        "user_id",
        string="Assigned Operations Officers",
    )
    lhi_authorized_user_ids = fields.Many2many(
        "res.users",
        "lhi_hub_authorized_user_rel",
        "warehouse_id",
        "user_id",
        string="Authorized Users",
    )
    lhi_default_receipt_location_id = fields.Many2one(
        "stock.location", string="Default Receipt Location", check_company=True
    )
    lhi_default_dispatch_location_id = fields.Many2one(
        "stock.location", string="Default Dispatch Location", check_company=True
    )
    lhi_quarantine_location_id = fields.Many2one(
        "stock.location", string="Quarantine Location", check_company=True
    )
    lhi_damaged_location_id = fields.Many2one(
        "stock.location", string="Damaged Items Location", check_company=True
    )
    lhi_returns_location_id = fields.Many2one(
        "stock.location", string="Returns Location", check_company=True
    )
    lhi_lease_location_id = fields.Many2one(
        "stock.location", string="Lease Equipment Location", check_company=True
    )

    @api.constrains(
        "lhi_default_receipt_location_id",
        "lhi_default_dispatch_location_id",
        "lhi_quarantine_location_id",
        "lhi_damaged_location_id",
        "lhi_returns_location_id",
        "lhi_lease_location_id",
    )
    def _check_lhi_hub_locations(self):
        for hub in self:
            descendants = self.env["stock.location"].search(
                [("id", "child_of", hub.view_location_id.id)]
            )
            for field_name in (
                "lhi_default_receipt_location_id",
                "lhi_default_dispatch_location_id",
                "lhi_quarantine_location_id",
                "lhi_damaged_location_id",
                "lhi_returns_location_id",
                "lhi_lease_location_id",
            ):
                location = hub[field_name]
                if location and location not in descendants:
                    raise ValidationError(
                        _("%s must be a storage location inside this HUB.")
                        % hub._fields[field_name].string
                    )

    @api.constrains(
        "lhi_operations_manager_id",
        "lhi_warehouse_officer_ids",
        "lhi_operations_officer_ids",
        "lhi_authorized_user_ids",
    )
    def _check_assignees_are_authorized(self):
        for hub in self:
            assigned = (
                hub.lhi_warehouse_officer_ids
                | hub.lhi_operations_officer_ids
                | hub.lhi_operations_manager_id
            )
            if assigned - hub.lhi_authorized_user_ids:
                raise ValidationError(
                    _(
                        "The Operations Manager and assigned officers must also "
                        "be listed as authorized HUB users."
                    )
                )

    def action_create_lhi_standard_locations(self):
        if not (
            self.env.user.has_group("lhi_security.group_lhi_operations_manager")
            or self.env.user.has_group("lhi_security.group_lhi_erp_admin")
        ):
            raise AccessError(
                _("Only Operations Managers may configure HUB locations.")
            )
        location_model = self.env["stock.location"]
        names = {
            "lhi_default_receipt_location_id": "Receiving Area",
            "nfi": "NFI Store",
            "medical": "Medical Equipment Store",
            "pharma": "Pharmaceutical Store",
            "consumables": "Consumables Store",
            "lhi_quarantine_location_id": "Quarantine",
            "lhi_damaged_location_id": "Damaged Items",
            "lhi_default_dispatch_location_id": "Dispatch Area",
            "lhi_lease_location_id": "Lease Equipment Area",
            "lhi_returns_location_id": "Returns Area",
        }
        for hub in self:
            updates = {}
            for key, name in names.items():
                location = location_model.search(
                    [
                        ("location_id", "=", hub.view_location_id.id),
                        ("name", "=", name),
                        ("company_id", "=", hub.company_id.id),
                    ],
                    limit=1,
                )
                if not location:
                    location = location_model.create(
                        {
                            "name": name,
                            "location_id": hub.view_location_id.id,
                            "usage": "internal",
                            "company_id": hub.company_id.id,
                        }
                    )
                if key.startswith("lhi_"):
                    updates[key] = location.id
            hub.write(updates)
        return True


class LhiHubAccessMixin(models.AbstractModel):
    _name = "lhi.hub.access.mixin"
    _description = "LHI HUB Authorization Boundary"

    def _lhi_user_has_any_group(self, groups):
        return any(self.env.user.has_group(group) for group in groups)

    def _lhi_assert_hub_access(self, hub, *, management=False):
        if not hub:
            raise ValidationError(_("A HUB is required."))
        if self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
            return True
        if self.env.user.has_group("lhi_security.group_lhi_director_operations"):
            return True
        if self.env.user.has_group("lhi_security.group_lhi_system_auditor"):
            if management:
                raise AccessError(_("System Auditors have read-only HUB access."))
            return True
        required = HUB_MANAGEMENT_GROUPS if management else HUB_EXECUTION_GROUPS
        if not self._lhi_user_has_any_group(required):
            raise AccessError(
                _("Your operational role does not permit this HUB action.")
            )
        if hub not in self.env.user.lhi_hub_ids:
            raise AccessError(
                _("You are not authorized for HUB %s.") % hub.display_name
            )
        return True

    def _lhi_assert_any_hub_access(self, hubs, *, management=False):
        for hub in hubs:
            self._lhi_assert_hub_access(hub, management=management)
        return True


class LhiHubStockService(models.AbstractModel):
    _name = "lhi.hub.stock.service"
    _description = "LHI HUB Stock Movement Service"

    @api.model
    def _lhi_create_picking(
        self,
        *,
        picking_type,
        source_location,
        destination_location,
        origin,
        move_specs,
        picking_values=None,
        reserve=False,
    ):
        if not move_specs:
            raise ValidationError(
                _("At least one positive stock movement is required.")
            )
        values = {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "origin": origin,
            "company_id": picking_type.company_id.id,
        }
        values.update(picking_values or {})
        stock_env = dict(self.env.context, lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN)
        picking = self.env["stock.picking"].with_context(stock_env).create(values)
        moves = self.env["stock.move"].with_context(stock_env)
        lots_by_move = {}
        for spec in move_specs:
            quantity = float(spec["quantity"])
            if quantity <= 0:
                continue
            move_values = {
                "name": spec["product"].display_name,
                "product_id": spec["product"].id,
                "product_uom_qty": quantity,
                "product_uom": spec.get("uom", spec["product"].uom_id).id,
                "picking_id": picking.id,
                "location_id": source_location.id,
                "location_dest_id": destination_location.id,
                "company_id": picking_type.company_id.id,
            }
            move_values.update(spec.get("values") or {})
            move = self.env["stock.move"].with_context(stock_env).create(move_values)
            if spec.get("lot") and reserve:
                lots_by_move[move.id] = spec["lot"]
            moves |= move
        if not moves:
            picking.unlink()
            raise ValidationError(
                _("At least one positive stock movement is required.")
            )
        picking.action_confirm()
        if reserve:
            for move in moves:
                lot = lots_by_move.get(move.id)
                if lot:
                    move.lot_ids = [(6, 0, lot.ids)]
            picking.action_assign()
            shortages = moves.filtered(
                lambda move: (
                    move.product_uom.compare(move.quantity, move.product_uom_qty) < 0
                )
            )
            if shortages:
                picking.do_unreserve()
                picking.action_cancel()
                raise ValidationError(
                    _("Insufficient available stock for: %s")
                    % ", ".join(shortages.mapped("product_id.display_name"))
                )
            for lot in moves.mapped("move_line_ids.lot_id"):
                lot._lhi_assert_issuable()
        return picking

    @api.model
    def _lhi_validate_picking(self, picking):
        for move in picking.move_ids:
            if move.product_uom.is_zero(move.quantity):
                move.quantity = move.product_uom_qty
            move.picked = True
        result = picking.with_context(
            skip_backorder=True,
            picking_ids_not_to_backorder=picking.ids,
            skip_sanity_check=False,
        ).button_validate()
        if isinstance(result, dict):
            raise UserError(
                _("The stock movement requires an interactive stock wizard.")
            )
        if picking.state != "done":
            raise UserError(_("The stock movement did not complete."))
        self.env["lhi.audit.log"].create_event(
            event_type="hub_operation",
            res_model=picking._name,
            res_id=picking.id,
            description=_("Validated HUB stock movement %s.") % picking.name,
        )
        destination_hub = picking.location_dest_id.warehouse_id
        if destination_hub:
            picking.move_line_ids.mapped("lot_id").sudo().with_context(
                lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"lhi_hub_id": destination_hub.id})
        return True
