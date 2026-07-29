# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


SEGMENT_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]*$")


class LhiAssetTagRule(models.Model):
    _name = "lhi.asset.tag.rule"
    _description = "LHI Asset Tag Rule"
    _order = "company_id, sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    organisation_prefix = fields.Char(
        required=True,
        default="LHI",
        help="First segment of every generated tag.",
    )
    lhi_owner_code = fields.Char(
        required=True,
        default="LHI",
        help="Second segment when the legal owner is the LHI company partner.",
    )
    separator = fields.Char(required=True, default="/")
    padding = fields.Integer(required=True, default=4)
    sequence_strategy = fields.Selection(
        [
            ("global", "One Global Organisation-wide Sequence"),
            ("owner", "Sequence per Project or Owner"),
            ("prefix", "Sequence per Project / State / Category Prefix"),
        ],
        required=True,
        default="global",
    )

    _name_company_unique = models.Constraint(
        "unique(name, company_id)", "Asset tag rule names must be unique per company."
    )

    @api.constrains(
        "active",
        "is_default",
        "company_id",
        "organisation_prefix",
        "lhi_owner_code",
        "separator",
        "padding",
    )
    def _check_rule(self):
        for rule in self:
            if rule.is_default and rule.active:
                other = self.search_count(
                    [
                        ("id", "!=", rule.id),
                        ("company_id", "=", rule.company_id.id),
                        ("active", "=", True),
                        ("is_default", "=", True),
                    ]
                )
                if other:
                    raise ValidationError(
                        _("Only one active default asset tag rule is allowed per company.")
                    )
            if rule.padding < 1 or rule.padding > 12:
                raise ValidationError(_("Tag sequence padding must be between 1 and 12."))
            if not rule.separator or len(rule.separator) != 1:
                raise ValidationError(_("The asset tag separator must be one character."))
            for value in (rule.organisation_prefix, rule.lhi_owner_code):
                if not SEGMENT_RE.fullmatch((value or "").strip().upper()):
                    raise ValidationError(
                        _("Tag prefixes may contain uppercase letters, numbers and hyphens.")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for field_name in ("organisation_prefix", "lhi_owner_code"):
                if field_name in vals:
                    vals[field_name] = (vals[field_name] or "").strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        for field_name in ("organisation_prefix", "lhi_owner_code"):
            if field_name in vals:
                vals[field_name] = (vals[field_name] or "").strip().upper()
        return super().write(vals)

    @api.model
    def default_rule(self, company):
        rule = self.search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("is_default", "=", True),
            ],
            order="sequence, id",
            limit=1,
        )
        if not rule:
            rule = self.search(
                [("company_id", "=", company.id), ("active", "=", True)],
                order="sequence, id",
                limit=1,
            )
        if not rule:
            raise UserError(
                _("Configure an active asset tag rule for company %s.")
                % company.display_name
            )
        return rule

    @api.model
    def _normalise_segment(self, value, label):
        segment = (value or "").strip().upper()
        if not SEGMENT_RE.fullmatch(segment):
            raise ValidationError(
                _("%(label)s '%(value)s' is not a valid asset-tag segment.")
                % {"label": label, "value": value or ""}
            )
        return segment

    def _segments_for_asset(self, asset):
        self.ensure_one()
        organisation = self._normalise_segment(
            self.organisation_prefix, _("Organisation prefix")
        )
        if asset.legal_owner_id == asset.company_id.partner_id:
            owner = self._normalise_segment(
                self.lhi_owner_code, _("LHI owner code")
            )
        else:
            owner = self._normalise_segment(
                asset.project_abbreviation
                or (asset.project_id.code if asset.project_id else ""),
                _("Project abbreviation"),
            )
        state = asset.registration_state_id
        state_code = state.lhi_asset_code or state.code if state else ""
        state_segment = self._normalise_segment(state_code, _("State code"))
        category_segment = self._normalise_segment(
            asset.category_id.code, _("Asset category code")
        )
        return organisation, owner, state_segment, category_segment

    def _scope_key(self, segments):
        self.ensure_one()
        if self.sequence_strategy == "global":
            return "GLOBAL"
        if self.sequence_strategy == "owner":
            return segments[1]
        return self.separator.join(segments)

    def _allocate_number(self, scope_key):
        """Atomically increment a prefix counter in PostgreSQL.

        The single parameterised UPSERT is necessary here: an ORM search/create
        pair can race under concurrent Odoo workers. The unique database
        constraint on (rule_id, scope_key) is the final duplicate boundary.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        self.env.cr.execute(
            """
            INSERT INTO lhi_asset_tag_counter
                (rule_id, scope_key, next_number,
                 create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, 2, %s, %s, %s, %s)
            ON CONFLICT (rule_id, scope_key)
            DO UPDATE
               SET next_number = lhi_asset_tag_counter.next_number + 1,
                   write_uid = EXCLUDED.write_uid,
                   write_date = EXCLUDED.write_date
            RETURNING next_number - 1
            """,
            (
                self.id,
                scope_key,
                self.env.user.id,
                self.env.user.id,
                now,
                now,
            ),
        )
        return self.env.cr.fetchone()[0]

    def _allocate_for_asset(self, asset):
        self.ensure_one()
        if asset.company_id != self.company_id:
            raise ValidationError(_("The asset tag rule belongs to another company."))
        segments = self._segments_for_asset(asset)
        scope_key = self._scope_key(segments)
        number = self._allocate_number(scope_key)
        sequence = str(number).zfill(self.padding)
        return self.separator.join((*segments, sequence)), number

    @api.model
    def parse_tag(self, tag):
        value = tag or ""
        parts = value.split("/")
        if len(parts) != 5 or not all(parts):
            return False
        if not all(SEGMENT_RE.fullmatch(part) for part in parts[:4]):
            return False
        if not parts[4].isdigit():
            return False
        return {
            "organisation": parts[0],
            "owner_or_project": parts[1],
            "state": parts[2],
            "category": parts[3],
            "sequence": int(parts[4]),
        }


class LhiAssetTagCounter(models.Model):
    _name = "lhi.asset.tag.counter"
    _description = "Atomic Asset Tag Counter"
    _rec_name = "scope_key"

    rule_id = fields.Many2one(
        "lhi.asset.tag.rule", required=True, ondelete="cascade", index=True
    )
    scope_key = fields.Char(required=True, index=True)
    next_number = fields.Integer(required=True, default=1)

    _rule_scope_unique = models.Constraint(
        "unique(rule_id, scope_key)",
        "An asset-tag counter already exists for this sequence scope.",
    )

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise ValidationError(
                _("Asset tag counters cannot be deleted because tags are permanent.")
            )
        return super().unlink()
