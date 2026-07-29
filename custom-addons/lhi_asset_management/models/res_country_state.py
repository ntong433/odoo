# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    lhi_asset_code = fields.Char(
        string="LHI Asset Tag Code",
        help="Optional state segment used in LHI asset tags, for example EBO or BAU.",
    )

    @api.constrains("lhi_asset_code")
    def _check_lhi_asset_code(self):
        for state in self:
            code = (state.lhi_asset_code or "").strip().upper()
            if code and not re.fullmatch(r"[A-Z0-9][A-Z0-9-]*", code):
                raise ValidationError(
                    _("LHI asset state codes may contain letters, numbers and hyphens.")
                )

    def write(self, vals):
        if "lhi_asset_code" in vals:
            vals["lhi_asset_code"] = (
                vals.get("lhi_asset_code") or ""
            ).strip().upper()
            for state in self:
                if (
                    vals["lhi_asset_code"] != (state.lhi_asset_code or "")
                    and "lhi.asset" in self.env
                    and self.env["lhi.asset"].search_count(
                        [
                            ("registration_state_id", "=", state.id),
                            ("asset_tag", "!=", False),
                        ]
                    )
                ):
                    raise ValidationError(
                        _(
                            "A state code used by tagged assets is immutable. "
                            "Create a controlled re-tag plan before changing it."
                        )
                    )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "lhi_asset_code" in vals:
                vals["lhi_asset_code"] = (
                    vals.get("lhi_asset_code") or ""
                ).strip().upper()
        return super().create(vals_list)
