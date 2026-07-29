# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class LhiAssetTransfer(models.Model):
    _name = "lhi.asset.transfer"
    _description = "Asset Transfer and Disposal Workflow"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, default=lambda self: _("New")
    )
    asset_id = fields.Many2one(
        "lhi.asset",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    transfer_type = fields.Selection(
        [
            ("handover", "Custody Handover"),
            ("location", "Location Move"),
            ("maintenance", "Send to Maintenance"),
            ("return", "Return"),
            ("loss_damage", "Loss or Damage"),
            ("write_off", "Disposal / Write-off"),
            ("donation", "Donation / Handover to Partner"),
        ],
        required=True,
        tracking=True,
    )
    source_custodian_id = fields.Many2one(
        related="asset_id.custodian_id", string="Current Custodian"
    )
    dest_custodian_id = fields.Many2one(
        "res.users", string="New Custodian", tracking=True
    )
    source_state_id = fields.Many2one(
        related="asset_id.state_id", string="Current State"
    )
    dest_state_id = fields.Many2one("res.country.state", string="New State")
    source_office_id = fields.Many2one(
        related="asset_id.office_id", string="Current Office"
    )
    dest_office_id = fields.Many2one("lhi.office", string="New Office")
    source_hub_id = fields.Many2one(related="asset_id.hub_id", string="Current HUB")
    dest_hub_id = fields.Many2one("stock.warehouse", string="New HUB")
    source_location_id = fields.Many2one(
        related="asset_id.location_id", string="Current Physical Location"
    )
    dest_location_id = fields.Many2one(
        "lhi.location", string="New Physical Location", tracking=True
    )
    destination_partner_id = fields.Many2one(
        "res.partner", string="Recipient"
    )
    source_project_id = fields.Many2one(
        related="asset_id.project_id", string="Current Project"
    )
    dest_project_id = fields.Many2one("lhi.project", string="New Project")
    source_funding_source_id = fields.Many2one(
        related="asset_id.funding_source_id", string="Current Funding Source"
    )
    dest_funding_source_id = fields.Many2one(
        "lhi.funding.source", string="New Funding Source"
    )
    source_legal_owner_id = fields.Many2one(
        related="asset_id.legal_owner_id", string="Current Legal Owner"
    )
    dest_legal_owner_id = fields.Many2one(
        "res.partner", string="New Legal Owner"
    )
    loss_outcome = fields.Selection(
        [("lost", "Lost"), ("stolen", "Stolen")],
        string="Loss Outcome",
    )
    justification = fields.Text(required=True)
    unfulfilled_notes = fields.Text()
    previous_asset_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("available", "Available"),
            ("assigned", "Assigned"),
            ("in_use", "In Use"),
            ("under_repair", "Under Repair"),
            ("in_transit", "In Transit"),
            ("lost", "Lost"),
            ("stolen", "Stolen"),
            ("disposed", "Disposed"),
            ("archived", "Archived"),
        ],
        readonly=True,
        copy=False,
    )
    approval_request_id = fields.Many2one(
        "lhi.approval.request", readonly=True, copy=False, ondelete="restrict"
    )
    lhi_approval_state = fields.Selection(
        related="approval_request_id.state",
        string="Approval Status",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted for Approval"),
            ("approved", "Approved"),
            ("completed", "Completed"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    company_id = fields.Many2one(
        related="asset_id.company_id", store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("lhi.asset.transfer")
                    or _("New")
                )
        return super().create(vals_list)

    @api.constrains("asset_id", "state")
    def _check_single_open_transfer(self):
        for transfer in self.filtered(lambda item: item.state not in ("completed", "cancel")):
            if self.search_count(
                [
                    ("id", "!=", transfer.id),
                    ("asset_id", "=", transfer.asset_id.id),
                    ("state", "not in", ("completed", "cancel")),
                ]
            ):
                raise ValidationError(
                    _("Asset %s already has an open transfer.")
                    % transfer.asset_id.display_name
                )

    def write(self, vals):
        protected = {
            "asset_id",
            "transfer_type",
            "source_custodian_id",
            "source_state_id",
            "source_office_id",
            "source_hub_id",
            "source_location_id",
            "approval_request_id",
            "state",
            "completed_by_id",
            "completed_at",
        }
        if protected.intersection(vals) and not self.env.context.get(
            "lhi_asset_transfer_system"
        ):
            raise AccessError(_("Use the transfer workflow actions to change this record."))
        if any(record.state != "draft" for record in self) and set(vals).intersection(
            {
                "dest_custodian_id",
                "dest_state_id",
                "dest_office_id",
                "dest_hub_id",
                "dest_location_id",
                "destination_partner_id",
                "dest_project_id",
                "dest_funding_source_id",
                "dest_legal_owner_id",
                "loss_outcome",
                "justification",
            }
        ):
            raise ValidationError(_("Submitted transfer details are immutable."))
        return super().write(vals)

    def _approval_document_type(self):
        self.ensure_one()
        return (
            "asset_disposal"
            if self.transfer_type in ("write_off", "donation")
            else "asset_transfer"
        )

    def action_submit(self):
        for transfer in self:
            if transfer.state != "draft":
                raise UserError(_("Only draft transfers can be submitted."))
            if transfer.asset_id.state in ("draft", "disposed", "archived"):
                raise UserError(
                    _("This asset cannot enter a transfer workflow in its current status.")
                )
            approval = self.env["lhi.approval.request"].create(
                {
                    "res_model": transfer._name,
                    "res_id": transfer.id,
                    "document_type": transfer._approval_document_type(),
                    "amount": transfer.asset_id.asset_value,
                    "currency_id": transfer.asset_id.currency_id.id,
                    "creator_id": self.env.user.id,
                    "project_id": transfer.asset_id.project_id.id,
                    "office_id": transfer.asset_id.office_id.id,
                    "funding_source_id": transfer.asset_id.funding_source_id.id,
                    "company_id": transfer.company_id.id,
                }
            )
            approval.action_submit()
            transfer.with_context(lhi_asset_transfer_system=True).write(
                {
                    "approval_request_id": approval.id,
                    "previous_asset_state": transfer.asset_id.state,
                    "state": "submitted",
                }
            )
            if transfer.transfer_type in ("location", "handover", "return"):
                transfer.asset_id.with_context(lhi_asset_system_write=True).write(
                    {"state": "in_transit"}
                )
        return True

    def action_mark_approved(self):
        for transfer in self:
            if (
                transfer.state != "submitted"
                or transfer.approval_request_id.state != "approved"
            ):
                raise UserError(
                    _("The configured approval route has not been completed.")
                )
            transfer.with_context(lhi_asset_transfer_system=True).write(
                {"state": "approved"}
            )
        return True

    def action_open_approval(self):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("Submit this transfer before opening its approval."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "lhi.approval.request",
            "res_id": self.approval_request_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_complete(self):
        if not (
            self.env.user.has_group("lhi_security.group_lhi_asset_officer")
            or self.env.user.has_group("lhi_security.group_lhi_asset_manager")
        ):
            raise AccessError(_("Only Asset Officers may complete asset movements."))
        for transfer in self:
            if transfer.state not in ("submitted", "approved"):
                raise UserError(_("The transfer is not ready for completion."))
            if transfer.approval_request_id.state != "approved":
                raise UserError(_("The approval route must be fully approved first."))
            vals = {}
            if transfer.dest_custodian_id:
                vals["custodian_id"] = transfer.dest_custodian_id.id
            if transfer.dest_state_id:
                vals["state_id"] = transfer.dest_state_id.id
            if transfer.dest_office_id:
                vals["office_id"] = transfer.dest_office_id.id
            if transfer.dest_hub_id:
                vals["hub_id"] = transfer.dest_hub_id.id
            if transfer.dest_location_id:
                vals["location_id"] = transfer.dest_location_id.id
            if transfer.dest_project_id:
                vals["project_id"] = transfer.dest_project_id.id
                vals["project_abbreviation"] = transfer.dest_project_id.code
            if transfer.dest_funding_source_id:
                vals["funding_source_id"] = transfer.dest_funding_source_id.id
            if transfer.dest_legal_owner_id:
                vals["legal_owner_id"] = transfer.dest_legal_owner_id.id

            if transfer.transfer_type == "maintenance":
                vals["state"] = "under_repair"
            elif transfer.transfer_type == "return":
                vals.update({"state": "available", "custodian_id": False})
            elif transfer.transfer_type == "loss_damage":
                if not transfer.loss_outcome:
                    raise ValidationError(
                        _("Select whether the asset was lost or stolen.")
                    )
                vals["state"] = transfer.loss_outcome
            elif transfer.transfer_type in ("write_off", "donation"):
                vals.update({"state": "disposed", "custodian_id": False})
                if transfer.dest_legal_owner_id:
                    vals["legal_owner_id"] = transfer.dest_legal_owner_id.id
            elif vals.get("custodian_id"):
                vals["state"] = "assigned"
            else:
                vals["state"] = "available"

            transfer.asset_id.with_context(
                lhi_asset_system_write=True,
                lhi_asset_movement_write=True,
            ).write(vals)
            transfer.with_context(lhi_asset_transfer_system=True).write(
                {
                    "state": "completed",
                    "completed_by_id": self.env.user.id,
                    "completed_at": fields.Datetime.now(),
                }
            )
            event = (
                "disposal"
                if transfer.transfer_type in ("write_off", "donation")
                else "movement"
            )
            transfer.asset_id._lhi_add_history(
                event,
                _("Completed asset workflow %s (%s).")
                % (
                    transfer.name,
                    dict(
                        transfer._fields["transfer_type"]._description_selection(
                            self.env
                        )
                    ).get(transfer.transfer_type, transfer.transfer_type),
                ),
                reference_model=transfer._name,
                reference_id=transfer.id,
            )
        return True

    def action_cancel(self):
        for transfer in self:
            if transfer.state in ("completed", "cancel"):
                raise UserError(_("This transfer can no longer be cancelled."))
            if (
                transfer.approval_request_id
                and transfer.approval_request_id.state == "under_review"
            ):
                raise UserError(
                    _("Return or reject the active approval before cancelling.")
                )
            if transfer.asset_id.state == "in_transit":
                transfer.asset_id.with_context(lhi_asset_system_write=True).write(
                    {"state": transfer.previous_asset_state or "available"}
                )
            transfer.with_context(lhi_asset_transfer_system=True).write(
                {"state": "cancel"}
            )
        return True

    def unlink(self):
        if any(record.state != "draft" for record in self):
            raise ValidationError(_("Submitted asset workflows cannot be deleted."))
        return super().unlink()
