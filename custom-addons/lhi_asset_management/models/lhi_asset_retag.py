# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class LhiAssetRetagRequest(models.Model):
    _name = "lhi.asset.retag.request"
    _description = "Controlled Asset Re-tag Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("New"), copy=False)
    asset_id = fields.Many2one(
        "lhi.asset", required=True, ondelete="restrict", tracking=True
    )
    previous_tag = fields.Char(required=True, readonly=True, copy=False)
    new_tag = fields.Char(readonly=True, copy=False)
    reason = fields.Text(required=True, tracking=True)
    requested_by_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )
    requested_at = fields.Datetime(
        required=True, default=fields.Datetime.now, readonly=True
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
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
        index=True,
    )
    company_id = fields.Many2one(
        related="asset_id.company_id", store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            asset = self.env["lhi.asset"].browse(vals.get("asset_id")).exists()
            if not asset or not asset.asset_tag or asset.state == "draft":
                raise ValidationError(
                    _("Only a confirmed, tagged asset can be submitted for re-tagging.")
                )
            vals["previous_tag"] = asset.asset_tag
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("lhi.asset.retag.request")
                    or _("New")
                )
        return super().create(vals_list)

    def write(self, vals):
        protected = {
            "asset_id",
            "previous_tag",
            "new_tag",
            "requested_by_id",
            "approved_by_id",
            "approved_at",
            "state",
        }
        if protected.intersection(vals) and not self.env.context.get(
            "lhi_asset_retag_system"
        ):
            raise AccessError(_("Use the re-tag workflow actions to change this request."))
        if any(request.state != "draft" for request in self) and set(vals).intersection(
            {"reason", "asset_id"}
        ):
            raise ValidationError(_("Submitted re-tag requests are immutable."))
        return super().write(vals)

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft re-tag requests can be submitted."))
            if not (request.reason or "").strip():
                raise ValidationError(_("A re-tag reason is required."))
            request.with_context(lhi_asset_retag_system=True).write(
                {"state": "submitted"}
            )
        return True

    def action_approve(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_manager"):
            raise AccessError(_("Only Asset Managers may approve re-tag requests."))
        for request in self:
            if request.state != "submitted":
                raise UserError(_("Only submitted re-tag requests can be approved."))
            if request.requested_by_id == self.env.user:
                raise UserError(_("You cannot approve your own re-tag request."))
            asset = request.asset_id
            if asset.asset_tag != request.previous_tag:
                raise ValidationError(
                    _("The asset tag changed after this request was submitted.")
                )
            rule = self.env["lhi.asset.tag.rule"].default_rule(asset.company_id)
            new_tag, number = rule._allocate_for_asset(asset)
            asset.with_context(
                lhi_asset_retag_write=True,
                lhi_asset_system_write=True,
                lhi_asset_skip_history=True,
            ).write(
                {
                    "asset_tag": new_tag,
                    "tag_generated_at": fields.Datetime.now(),
                    "tag_generated_by_id": self.env.user.id,
                    "tag_rule_id": rule.id,
                    "tag_sequence_number": number,
                    "legacy_tag": False,
                    "tag_validation_status": "valid",
                }
            )
            request.with_context(lhi_asset_retag_system=True).write(
                {
                    "new_tag": new_tag,
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "state": "approved",
                }
            )
            asset._lhi_add_history(
                "tag",
                _(
                    "Approved re-tag from %(old)s to %(new)s. Reason: %(reason)s"
                )
                % {
                    "old": request.previous_tag,
                    "new": new_tag,
                    "reason": request.reason,
                },
                field_name="asset_tag",
                old_value=request.previous_tag,
                new_value=new_tag,
                reference_model=request._name,
                reference_id=request.id,
            )
            self.env["lhi.audit.log"].create_event(
                event_type="write_sensitive_field",
                res_model=asset._name,
                res_id=asset.id,
                description=_("Asset re-tag approved: %s → %s")
                % (request.previous_tag, new_tag),
            )
        return True

    def action_reject(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_manager"):
            raise AccessError(_("Only Asset Managers may reject re-tag requests."))
        for request in self:
            if request.state != "submitted":
                raise UserError(_("Only submitted re-tag requests can be rejected."))
            if not (request.rejection_reason or "").strip():
                raise ValidationError(_("A rejection reason is required."))
            request.with_context(lhi_asset_retag_system=True).write(
                {"state": "rejected"}
            )
        return True

    def action_cancel(self):
        for request in self:
            if request.requested_by_id != self.env.user:
                raise AccessError(_("Only the requester may cancel this request."))
            if request.state not in ("draft", "submitted"):
                raise UserError(_("This re-tag request can no longer be cancelled."))
            request.with_context(lhi_asset_retag_system=True).write(
                {"state": "cancelled"}
            )
        return True

    def unlink(self):
        if any(request.state != "draft" for request in self):
            raise ValidationError(_("Submitted re-tag requests cannot be deleted."))
        return super().unlink()
