# -*- coding: utf-8 -*-
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


TRACKED_HISTORY_FIELDS = OrderedDict(
    [
        ("custodian_id", "custody"),
        ("state_id", "movement"),
        ("office_id", "movement"),
        ("hub_id", "movement"),
        ("location_id", "movement"),
        ("condition_id", "condition"),
        ("state", "status"),
        ("project_id", "project"),
        ("legal_owner_id", "ownership"),
        ("funding_source_id", "funding"),
        ("asset_tag", "tag"),
    ]
)


class LhiAsset(models.Model):
    _name = "lhi.asset"
    _description = "LHI Operational Asset"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "asset_tag, name, id"

    name = fields.Char(string="Asset Name", required=True, tracking=True)
    description = fields.Text(string="Asset Description")
    asset_tag = fields.Char(
        string="Asset Tag",
        copy=False,
        index=True,
        tracking=True,
        help="Generated tags become immutable when the asset is confirmed.",
    )
    serial_number = fields.Char(
        string="Manufacturer Serial Number", copy=False, index=True, tracking=True
    )
    category_id = fields.Many2one(
        "lhi.asset.category",
        string="Asset Category",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    category_code = fields.Char(
        related="category_id.code", string="Asset Category Code", store=True
    )
    condition_id = fields.Many2one(
        "lhi.asset.condition",
        string="Asset Condition",
        ondelete="restrict",
        tracking=True,
        default=lambda self: self.env.ref(
            "lhi_asset_management.asset_condition_new",
            raise_if_not_found=False,
        ),
    )
    # Kept only so an upgrade can map values created by the original addon.
    condition = fields.Selection(
        [
            ("new", "New"),
            ("good", "Good / Operational"),
            ("fair", "Fair / Needs Repair"),
            ("poor", "Poor / End of Life"),
            ("broken", "Broken / Written-off"),
        ],
        string="Legacy Condition",
        readonly=True,
        copy=False,
    )

    acquisition_date = fields.Date(tracking=True)
    acquisition_type = fields.Selection(
        [
            ("purchased", "Purchased"),
            ("donated", "Donated"),
            ("partner_contribution", "Partner Contribution"),
            ("in_kind", "In-kind Contribution"),
            ("transferred", "Transferred"),
            ("leased_in", "Leased In"),
            ("other", "Other"),
        ],
        tracking=True,
    )
    acquisition_source_id = fields.Many2one(
        "res.partner", string="Acquisition Source", tracking=True
    )
    legal_owner_id = fields.Many2one(
        "res.partner",
        string="Legal Owner",
        tracking=True,
        default=lambda self: self.env.company.partner_id,
    )
    funding_source_id = fields.Many2one(
        "lhi.funding.source", string="Funding Source", tracking=True
    )
    donor_id = fields.Many2one("res.partner", string="Donor or Partner", tracking=True)
    project_id = fields.Many2one("lhi.project", string="Project", tracking=True)
    project_abbreviation = fields.Char(
        string="Project Abbreviation",
        tracking=True,
        help="Snapshot used in the asset tag. Defaults to the project code.",
    )
    programme_id = fields.Many2one("lhi.programme", string="Programme", tracking=True)
    award_id = fields.Many2one("lhi.award", string="Grant or Award", tracking=True)
    grant_id = fields.Char(
        string="Legacy Grant Reference",
        tracking=True,
        help="Preserved for records created by earlier module versions.",
    )
    purchase_order_id = fields.Many2one(
        "lhi.purchase.order", string="Purchase Order", tracking=True
    )

    registration_state_id = fields.Many2one(
        "res.country.state",
        string="Registration / Origin State",
        ondelete="restrict",
        tracking=True,
        help="This state is frozen into a generated asset tag.",
    )
    state_id = fields.Many2one(
        "res.country.state", string="Current State", ondelete="restrict", tracking=True
    )
    state_code = fields.Char(
        string="State Code", compute="_compute_state_code", store=True
    )
    office_id = fields.Many2one("lhi.office", string="Office", tracking=True)
    hub_id = fields.Many2one(
        "stock.warehouse", string="Current HUB", ondelete="restrict", tracking=True
    )
    custodian_id = fields.Many2one(
        "res.users", string="Current Custodian", tracking=True
    )
    location_id = fields.Many2one(
        "lhi.location", string="Current Physical Location", tracking=True
    )

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    asset_value = fields.Monetary(
        string="Purchase or Declared Value", currency_field="currency_id", tracking=True
    )
    purchase_value = fields.Monetary(
        string="Purchase Value", currency_field="currency_id", tracking=True
    )
    declared_value = fields.Monetary(
        string="Donor / Partner Declared Value",
        currency_field="currency_id",
        tracking=True,
    )
    value_source = fields.Selection(
        [
            ("purchase_price", "Purchase Price"),
            ("donor_declared", "Donor-declared Value"),
            ("partner_declared", "Partner-declared Value"),
            ("replacement", "Estimated Replacement Value"),
            ("legacy", "Imported Legacy Value"),
            ("manual", "Approved Manual Valuation"),
        ],
        string="Operational Value Source",
        tracking=True,
    )
    value_date = fields.Date(string="Operational Value Date", tracking=True)
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency", store=True
    )
    operational_value_company = fields.Monetary(
        string="Operational Asset Value",
        currency_field="company_currency_id",
        compute="_compute_operational_value_company",
        store=True,
        help="Asset value converted to the company currency without accounting entries.",
    )
    donor_restrictions = fields.Text()
    ownership_restriction = fields.Text(
        string="Legacy Ownership / Disposal Restrictions"
    )
    warranty_information = fields.Text()
    warranty_expiry = fields.Date(tracking=True)
    supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_asset_attachment_rel",
        "asset_id",
        "attachment_id",
        string="Supporting Documents",
        copy=False,
    )
    supporting_document_count = fields.Integer(
        compute="_compute_supporting_document_count"
    )
    notes = fields.Html()

    barcode_value = fields.Char(compute="_compute_codes")
    qr_code_value = fields.Char(compute="_compute_codes")
    legacy_tag = fields.Boolean(copy=False, index=True, tracking=True)
    tag_validation_status = fields.Selection(
        [
            ("unvalidated", "Unvalidated"),
            ("valid", "Valid LHI Convention"),
            ("nonstandard", "Preserved Non-standard Legacy Tag"),
            ("invalid", "Invalid"),
        ],
        default="unvalidated",
        required=True,
        copy=False,
        tracking=True,
    )
    tag_generated_at = fields.Datetime(readonly=True, copy=False)
    tag_generated_by_id = fields.Many2one(
        "res.users", string="Tag Generated By", readonly=True, copy=False
    )
    tag_rule_id = fields.Many2one(
        "lhi.asset.tag.rule",
        string="Applied Tag Rule",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    tag_sequence_number = fields.Integer(readonly=True, copy=False)

    state = fields.Selection(
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
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    transfer_ids = fields.One2many(
        "lhi.asset.transfer", "asset_id", string="Transfer History"
    )
    history_ids = fields.One2many(
        "lhi.asset.history", "asset_id", string="Lifecycle History"
    )
    retag_request_ids = fields.One2many(
        "lhi.asset.retag.request", "asset_id", string="Re-tag Requests"
    )
    import_batch_id = fields.Many2one(
        "lhi.asset.import.batch", readonly=True, copy=False, ondelete="restrict"
    )

    is_lhi_owned = fields.Boolean(compute="_compute_ownership", store=True)
    is_project_asset = fields.Boolean(compute="_compute_ownership", store=True)

    _asset_tag_unique = models.Constraint(
        "unique(asset_tag)", "Asset tags must be unique across LHI ERP."
    )
    _serial_company_unique = models.Constraint(
        "unique(serial_number, company_id)",
        "A manufacturer serial number can only be used once per company.",
    )

    @api.depends("state_id", "state_id.code", "state_id.lhi_asset_code")
    def _compute_state_code(self):
        for asset in self:
            asset.state_code = (
                asset.state_id.lhi_asset_code or asset.state_id.code or ""
            ).upper()

    @api.depends("asset_tag")
    def _compute_codes(self):
        for asset in self:
            asset.barcode_value = asset.asset_tag or False
            asset.qr_code_value = asset.asset_tag or False

    @api.depends("supporting_document_ids")
    def _compute_supporting_document_count(self):
        for asset in self:
            asset.supporting_document_count = len(asset.supporting_document_ids)

    @api.depends("legal_owner_id", "project_id", "company_id")
    def _compute_ownership(self):
        for asset in self:
            asset.is_lhi_owned = bool(
                asset.legal_owner_id
                and asset.legal_owner_id == asset.company_id.partner_id
            )
            asset.is_project_asset = bool(asset.project_id and not asset.is_lhi_owned)

    @api.depends(
        "asset_value",
        "currency_id",
        "company_id",
        "company_id.currency_id",
        "value_date",
        "acquisition_date",
    )
    def _compute_operational_value_company(self):
        for asset in self:
            if not asset.currency_id or not asset.company_id.currency_id:
                asset.operational_value_company = asset.asset_value
                continue
            conversion_date = (
                asset.value_date
                or asset.acquisition_date
                or fields.Date.context_today(asset)
            )
            asset.operational_value_company = asset.currency_id._convert(
                asset.asset_value,
                asset.company_id.currency_id,
                asset.company_id,
                conversion_date,
            )

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and not self.project_abbreviation:
            self.project_abbreviation = self.project_id.code
        if self.project_id and not self.office_id:
            self.office_id = self.project_id.office_id
        if self.project_id and not self.award_id:
            self.award_id = self.project_id.award_id

    @api.model_create_multi
    def create(self, vals_list):
        assets = self.browse()
        for vals in vals_list:
            if vals.get("asset_tag") in ("New", "/"):
                vals["asset_tag"] = False
            project = (
                self.env["lhi.project"].browse(vals["project_id"])
                if vals.get("project_id")
                else self.env["lhi.project"]
            )
            if project and not vals.get("project_abbreviation"):
                vals["project_abbreviation"] = project.code
            asset = super().create(vals)
            if asset.asset_tag:
                classification = asset._lhi_classify_existing_tag(asset.asset_tag)
                asset.with_context(lhi_asset_system_write=True).write(classification)
            asset._lhi_add_history(
                "acquisition",
                _("Asset registered in LHI ERP."),
            )
            assets |= asset
        return assets

    def write(self, vals):
        controlled_movement_fields = {
            "state_id",
            "office_id",
            "hub_id",
            "location_id",
            "project_id",
            "legal_owner_id",
            "funding_source_id",
        }
        if (
            controlled_movement_fields.intersection(vals)
            and not self.env.context.get("lhi_asset_movement_write")
        ):
            confirmed = self.filtered(lambda asset: asset.state != "draft")
            if confirmed:
                raise AccessError(
                    _(
                        "Confirmed location, project, ownership, and funding "
                        "changes must use an approved asset workflow."
                    )
                )
        if (
            "registration_state_id" in vals
            and not self.env.context.get("lhi_asset_movement_write")
            and any(asset.tag_generated_at for asset in self)
        ):
            raise ValidationError(
                _("The registration state is immutable after tag generation.")
            )
        if "asset_tag" in vals:
            for asset in self:
                if (
                    asset.asset_tag
                    and vals.get("asset_tag") != asset.asset_tag
                    and asset.state != "draft"
                    and not self.env.context.get("lhi_asset_retag_write")
                ):
                    raise ValidationError(
                        _(
                            "Confirmed asset tags are immutable. Use an approved "
                            "re-tag request."
                        )
                    )
        if "state" in vals and not self.env.context.get("lhi_asset_system_write"):
            raise AccessError(_("Use the asset lifecycle actions to change status."))

        snapshots = {}
        watched = set(vals).intersection(TRACKED_HISTORY_FIELDS)
        if watched and not self.env.context.get("lhi_asset_skip_history"):
            for asset in self:
                snapshots[asset.id] = {
                    field_name: asset._lhi_history_display(field_name)
                    for field_name in watched
                }
        result = super().write(vals)
        if snapshots:
            for asset in self:
                for field_name in watched:
                    old_value = snapshots[asset.id][field_name]
                    new_value = asset._lhi_history_display(field_name)
                    if old_value != new_value:
                        asset._lhi_add_history(
                            TRACKED_HISTORY_FIELDS[field_name],
                            _("%(field)s changed from '%(old)s' to '%(new)s'.")
                            % {
                                "field": asset._fields[field_name].string,
                                "old": old_value or _("Empty"),
                                "new": new_value or _("Empty"),
                            },
                            field_name=field_name,
                            old_value=old_value,
                            new_value=new_value,
                        )
        return result

    def unlink(self):
        if self.env.context.get("lhi_asset_import_rollback"):
            return super().unlink()
        if not self.env.user.has_group("lhi_security.group_lhi_asset_manager"):
            raise AccessError(_("Only Asset Managers may delete draft asset records."))
        if any(asset.state != "draft" or asset.history_ids for asset in self):
            raise ValidationError(
                _("Assets with lifecycle history must be archived, not deleted.")
            )
        return super().unlink()

    def _lhi_history_display(self, field_name):
        self.ensure_one()
        field = self._fields[field_name]
        value = self[field_name]
        if field.type == "many2one":
            return value.display_name if value else ""
        if field.type == "selection":
            return dict(field._description_selection(self.env)).get(value, value or "")
        return str(value) if value not in (False, None) else ""

    def _lhi_add_history(
        self,
        event_type,
        description,
        *,
        field_name=False,
        old_value=False,
        new_value=False,
        reference_model=False,
        reference_id=False,
    ):
        self.ensure_one()
        return (
            self.env["lhi.asset.history"]
            .sudo()
            .with_context(lhi_asset_history_write=True)
            .create(
                {
                    "asset_id": self.id,
                    "event_type": event_type,
                    "description": description,
                    "field_name": field_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "reference_model": reference_model,
                    "reference_id": reference_id or 0,
                    "user_id": self.env.user.id,
                    "company_id": self.company_id.id,
                }
            )
        )

    def _lhi_classify_existing_tag(self, tag):
        self.ensure_one()
        parsed = self.env["lhi.asset.tag.rule"].parse_tag(tag)
        return {
            "legacy_tag": True,
            "tag_validation_status": "valid" if parsed else "nonstandard",
        }

    def _lhi_validate_confirmation(self):
        for asset in self:
            missing = []
            for field_name in (
                "category_id",
                "condition_id",
                "registration_state_id",
                "legal_owner_id",
                "currency_id",
            ):
                if not asset[field_name]:
                    missing.append(asset._fields[field_name].string)
            if missing:
                raise ValidationError(
                    _("Complete these fields before confirmation: %s")
                    % ", ".join(missing)
                )

    def action_generate_tag(self):
        for asset in self:
            if asset.asset_tag:
                raise ValidationError(
                    _("Asset %s already has a tag.") % asset.display_name
                )
            asset._lhi_validate_confirmation()
            asset._lhi_assign_generated_tag()
        return True

    def _lhi_assign_generated_tag(self):
        self.ensure_one()
        rule = self.env["lhi.asset.tag.rule"].default_rule(self.company_id)
        tag, number = rule._allocate_for_asset(self)
        self.with_context(
            lhi_asset_system_write=True,
            lhi_asset_skip_history=True,
        ).write(
            {
                "asset_tag": tag,
                "tag_generated_at": fields.Datetime.now(),
                "tag_generated_by_id": self.env.user.id,
                "tag_rule_id": rule.id,
                "tag_sequence_number": number,
                "legacy_tag": False,
                "tag_validation_status": "valid",
            }
        )
        self._lhi_add_history(
            "tagging",
            _("Generated asset tag %s using rule %s.") % (tag, rule.display_name),
            field_name="asset_tag",
            new_value=tag,
        )
        return tag

    def action_confirm(self):
        self._lhi_validate_confirmation()
        for asset in self:
            if asset.state != "draft":
                raise UserError(_("Only draft assets can be confirmed."))
            if not asset.asset_tag:
                asset._lhi_assign_generated_tag()
            asset.with_context(lhi_asset_system_write=True).write(
                {"state": "available"}
            )
            asset._lhi_add_history("registration", _("Asset registration confirmed."))
        return True

    def action_assign(self):
        for asset in self:
            if not asset.custodian_id:
                raise ValidationError(_("Select a custodian before assignment."))
            if asset.state not in ("available", "assigned", "in_use"):
                raise UserError(_("This asset cannot be assigned from its current status."))
            asset.with_context(lhi_asset_system_write=True).write(
                {"state": "assigned"}
            )
        return True

    def action_mark_in_use(self):
        for asset in self:
            if asset.state not in ("available", "assigned"):
                raise UserError(_("This asset cannot be marked in use."))
            asset.with_context(lhi_asset_system_write=True).write({"state": "in_use"})
        return True

    def action_send_for_repair(self):
        self.with_context(lhi_asset_system_write=True).write(
            {"state": "under_repair"}
        )
        return True

    def action_return_available(self):
        self.with_context(lhi_asset_system_write=True).write({"state": "available"})
        return True

    def action_archive_asset(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_manager"):
            raise AccessError(_("Only Asset Managers may archive assets."))
        self.with_context(lhi_asset_system_write=True).write(
            {"state": "archived", "active": False}
        )
        return True

    def action_open_supporting_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asset Supporting Documents"),
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.supporting_document_ids.ids)],
        }

    @api.model
    def _dashboard_group(self, field_name, *, measure=False, groupby=None):
        groupby = groupby or field_name
        aggregates = (
            ["operational_value_company:sum"] if measure else ["__count"]
        )
        rows = self.read_group(
            [],
            [field_name] + aggregates,
            [groupby],
            lazy=False,
        )
        result = []
        for row in rows:
            grouped = row.get(groupby, row.get(field_name))
            if isinstance(grouped, (list, tuple)):
                group_id, label = grouped[0], grouped[1]
                domain = [(field_name, "=", group_id)]
            else:
                field = self._fields[field_name]
                label = grouped or _("Unspecified")
                if field.type == "selection" and grouped:
                    label = dict(field._description_selection(self.env)).get(
                        grouped, grouped
                    )
                domain = [(field_name, "=", grouped or False)]
            value = (
                row.get("operational_value_company", 0.0)
                if measure
                else row.get("__count", 0)
            )
            result.append(
                {
                    "label": label or _("Unspecified"),
                    "value": value,
                    "domain": row.get("__domain", domain),
                }
            )
        return result

    @api.model
    def get_asset_dashboard_data(self):
        """Return record-rule-aware metrics; intentionally never uses sudo()."""
        self.check_access("read")
        count = self.search_count
        total_value = self.read_group(
            [], ["operational_value_company:sum"], []
        )[0].get("operational_value_company", 0.0)
        cards = [
            {"key": "total", "label": _("Total Assets"), "value": count([]), "domain": []},
            {
                "key": "value",
                "label": _("Total Operational Asset Value"),
                "value": total_value,
                "domain": [],
                "monetary": True,
            },
        ]
        cards.extend(
            [
            {
                "key": state,
                "label": label,
                "value": count([("state", "in", states)]),
                "domain": [("state", "in", states)],
            }
            for state, label, states in (
                ("available", _("Available Assets"), ["available"]),
                ("assigned", _("Assigned Assets"), ["assigned"]),
                ("in_use", _("Assets in Use"), ["in_use"]),
                ("under_repair", _("Assets Under Repair"), ["under_repair"]),
                ("lost_stolen", _("Lost or Stolen Assets"), ["lost", "stolen"]),
                ("disposed", _("Disposed Assets"), ["disposed"]),
            )
            ]
        )
        cards.extend(
            [
                {
                    "key": "damaged",
                    "label": _("Damaged Assets"),
                    "value": count([("condition_id.code", "=", "damaged")]),
                    "domain": [("condition_id.code", "=", "damaged")],
                },
                {
                    "key": "lhi_owned",
                    "label": _("LHI-owned Assets"),
                    "value": count([("is_lhi_owned", "=", True)]),
                    "domain": [("is_lhi_owned", "=", True)],
                },
                {
                    "key": "project",
                    "label": _("Project Assets"),
                    "value": count([("is_project_asset", "=", True)]),
                    "domain": [("is_project_asset", "=", True)],
                },
                {
                    "key": "donated",
                    "label": _("Donated Assets"),
                    "value": count([("acquisition_type", "=", "donated")]),
                    "domain": [("acquisition_type", "=", "donated")],
                },
                {
                    "key": "untagged",
                    "label": _("Assets Without Tags"),
                    "value": count([("asset_tag", "=", False)]),
                    "domain": [("asset_tag", "=", False)],
                },
                {
                    "key": "legacy",
                    "label": _("Legacy-tagged Assets"),
                    "value": count([("legacy_tag", "=", True)]),
                    "domain": [("legacy_tag", "=", True)],
                },
                {
                    "key": "hub_assets",
                    "label": _("Assets by Current HUB"),
                    "value": count([("hub_id", "!=", False)]),
                    "domain": [("hub_id", "!=", False)],
                },
            ]
        )
        charts = [
            {"key": "category", "label": _("Assets by Category"), "segments": self._dashboard_group("category_id")},
            {"key": "state", "label": _("Assets by State"), "segments": self._dashboard_group("state_id")},
            {"key": "project", "label": _("Assets by Project"), "segments": self._dashboard_group("project_id")},
            {"key": "programme", "label": _("Assets by Programme"), "segments": self._dashboard_group("programme_id")},
            {"key": "condition", "label": _("Assets by Condition"), "segments": self._dashboard_group("condition_id")},
            {"key": "acquisition_type", "label": _("Assets by Acquisition Type"), "segments": self._dashboard_group("acquisition_type")},
            {"key": "acquisition_source", "label": _("Assets by Acquisition Source"), "segments": self._dashboard_group("acquisition_source_id")},
            {"key": "owner", "label": _("Assets by Legal Owner"), "segments": self._dashboard_group("legal_owner_id")},
            {"key": "hub", "label": _("Assets by Current HUB"), "segments": self._dashboard_group("hub_id")},
            {"key": "value_project", "label": _("Asset Value by Project"), "segments": self._dashboard_group("project_id", measure=True), "monetary": True},
            {"key": "value_state", "label": _("Asset Value by State"), "segments": self._dashboard_group("state_id", measure=True), "monetary": True},
            {"key": "value_source", "label": _("Asset Value by Source"), "segments": self._dashboard_group("acquisition_source_id", measure=True), "monetary": True},
            {
                "key": "trend",
                "label": _("Asset Acquisition Trend by Year"),
                "segments": self._dashboard_group(
                    "acquisition_date", groupby="acquisition_date:year"
                ),
            },
        ]
        return {
            "cards": cards,
            "charts": charts,
            "currency": self.env.company.currency_id.symbol,
        }


class LhiAssetCategory(models.Model):
    _name = "lhi.asset.category"
    _description = "LHI Asset Category"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", index=True)

    _code_company_unique = models.Constraint(
        "unique(code, company_id)", "Asset category codes must be unique per company."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["code"] = (vals.get("code") or "").strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals:
            vals["code"] = (vals["code"] or "").strip().upper()
            for category in self:
                if (
                    vals["code"] != category.code
                    and self.env["lhi.asset"].search_count(
                        [("category_id", "=", category.id), ("asset_tag", "!=", False)]
                    )
                ):
                    raise ValidationError(
                        _(
                            "A category code used by tagged assets is immutable. "
                            "Archive it and create a new category instead."
                        )
                    )
        return super().write(vals)


class LhiAssetCondition(models.Model):
    _name = "lhi.asset.condition"
    _description = "LHI Asset Condition"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", index=True)

    _code_company_unique = models.Constraint(
        "unique(code, company_id)", "Asset condition codes must be unique per company."
    )


class LhiAssetHistory(models.Model):
    _name = "lhi.asset.history"
    _description = "Immutable Asset Lifecycle History"
    _order = "event_date desc, id desc"

    asset_id = fields.Many2one(
        "lhi.asset", required=True, ondelete="cascade", index=True
    )
    event_date = fields.Datetime(
        required=True, default=fields.Datetime.now, readonly=True, index=True
    )
    event_type = fields.Selection(
        [
            ("acquisition", "Acquisition"),
            ("registration", "Registration"),
            ("tagging", "Tagging"),
            ("receipt", "Receipt"),
            ("custody", "Assignment / Return"),
            ("movement", "Transfer / Movement"),
            ("condition", "Condition"),
            ("status", "Status"),
            ("project", "Project Assignment"),
            ("ownership", "Ownership"),
            ("funding", "Funding Source"),
            ("maintenance", "Maintenance"),
            ("loss_damage", "Loss or Damage"),
            ("disposal", "Disposal"),
            ("tag", "Tag Change"),
            ("import", "Legacy Import"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    description = fields.Text(required=True, readonly=True)
    field_name = fields.Char(readonly=True)
    old_value = fields.Text(readonly=True)
    new_value = fields.Text(readonly=True)
    user_id = fields.Many2one("res.users", required=True, readonly=True)
    reference_model = fields.Char(readonly=True)
    reference_id = fields.Integer(readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("lhi_asset_history_write"):
            raise AccessError(_("Asset history can only be written by lifecycle actions."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Asset lifecycle history is immutable."))

    def unlink(self):
        if self.env.context.get("module_uninstall") or self.env.context.get(
            "lhi_asset_import_rollback"
        ):
            return super().unlink()
        raise AccessError(_("Asset lifecycle history is immutable."))


class LhiLocation(models.Model):
    _name = "lhi.location"
    _description = "LHI Physical Location"
    _order = "name"

    name = fields.Char(string="Location Name", required=True)
    type = fields.Selection(
        [
            ("hq", "Headquarters"),
            ("field", "Field Office"),
            ("warehouse", "HUB"),
            ("project", "Project Site"),
        ],
        required=True,
    )
    state_id = fields.Many2one("res.country.state")
    office_id = fields.Many2one("lhi.office")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
