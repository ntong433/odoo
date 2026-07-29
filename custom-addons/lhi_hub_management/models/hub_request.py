# -*- coding: utf-8 -*-
import base64
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hub_structure import LHI_HUB_SYSTEM_TOKEN


MATERIAL_REQUEST_FIELDS = {
    "requesting_hub_id",
    "supplying_hub_id",
    "project_id",
    "programme_id",
    "award_id",
    "donor_id",
    "activity_id",
    "purpose",
    "priority",
    "emergency",
    "approval_matrix_id",
    "line_ids",
}

SYSTEM_REQUEST_FIELDS = {
    "state",
    "approval_request_id",
    "quantities_locked",
    "quantities_locked_at",
    "quantities_locked_by_id",
    "document_version_number",
    "current_document_version_id",
    "opensign_request_id",
    "provider_request_id",
    "provider_status",
    "integration_error_code",
    "integration_error_message",
    "source_pdf_hash",
    "signed_pdf_hash",
    "audit_certificate_hash",
    "approval_completed_at",
    "reservation_picking_id",
}


class LhiApprovalMatrix(models.Model):
    _inherit = "lhi.approval.matrix"

    document_type = fields.Selection(
        selection_add=[("hub_stock_request", "HUB Stock Request")],
        ondelete={"hub_stock_request": "cascade"},
    )
    lhi_requesting_hub_ids = fields.Many2many(
        "stock.warehouse",
        "lhi_matrix_requesting_hub_rel",
        "matrix_id",
        "warehouse_id",
        string="Requesting HUBs",
    )
    lhi_supplying_hub_ids = fields.Many2many(
        "stock.warehouse",
        "lhi_matrix_supplying_hub_rel",
        "matrix_id",
        "warehouse_id",
        string="Supplying HUBs",
    )
    lhi_inter_state = fields.Selection(
        [("any", "Any"), ("yes", "Inter-state Only"), ("no", "Same-state Only")],
        default="any",
    )
    lhi_priority = fields.Selection(
        [
            ("any", "Any"),
            ("routine", "Routine"),
            ("urgent", "Urgent"),
            ("critical", "Critical"),
        ],
        default="any",
    )
    lhi_emergency_rule = fields.Selection(
        [
            ("any", "Any"),
            ("only", "Emergency Requests Only"),
            ("exclude", "Exclude Emergency Requests"),
        ],
        default="any",
    )
    lhi_item_category_ids = fields.Many2many("product.category")
    lhi_product_ids = fields.Many2many("product.product")
    lhi_state_ids = fields.Many2many(
        "res.country.state",
        "lhi_matrix_hub_state_rel",
        "matrix_id",
        "state_id",
        string="Requesting HUB States",
    )
    lhi_programme_ids = fields.Many2many(
        "lhi.programme",
        "lhi_matrix_hub_programme_rel",
        "matrix_id",
        "programme_id",
        string="Programmes",
    )
    lhi_donor_partner_ids = fields.Many2many(
        "res.partner",
        "lhi_matrix_hub_donor_rel",
        "matrix_id",
        "partner_id",
        string="Donors or Partners",
    )
    lhi_min_quantity = fields.Float(string="Minimum Total Requested Quantity")
    lhi_max_quantity = fields.Float(
        string="Maximum Total Requested Quantity",
        help="Zero means no maximum.",
    )
    lhi_requires_pharmaceuticals = fields.Boolean()
    lhi_requires_controlled_items = fields.Boolean()
    lhi_requires_serialized = fields.Boolean(string="Requires Serialised Equipment")
    lhi_requires_consignment_restriction = fields.Boolean(
        string="Requires Restricted Consignment"
    )
    lhi_effective_from = fields.Date()
    lhi_effective_to = fields.Date()

    @api.constrains(
        "lhi_min_quantity",
        "lhi_max_quantity",
        "lhi_effective_from",
        "lhi_effective_to",
    )
    def _check_lhi_hub_criteria_ranges(self):
        for matrix in self:
            if matrix.lhi_min_quantity < 0 or matrix.lhi_max_quantity < 0:
                raise ValidationError(
                    _("HUB matrix quantity limits cannot be negative.")
                )
            if (
                matrix.lhi_max_quantity
                and matrix.lhi_min_quantity > matrix.lhi_max_quantity
            ):
                raise ValidationError(
                    _("Minimum HUB quantity cannot exceed the maximum.")
                )
            if (
                matrix.lhi_effective_from
                and matrix.lhi_effective_to
                and matrix.lhi_effective_from > matrix.lhi_effective_to
            ):
                raise ValidationError(
                    _("HUB matrix effective-from date cannot follow its end date.")
                )

    @api.constrains("line_ids", "document_type")
    def _check_lhi_hub_route_hierarchy(self):
        director = self.env.ref(
            "lhi_security.group_lhi_director_operations", raise_if_not_found=False
        )
        ned = self.env.ref("lhi_security.group_lhi_ned", raise_if_not_found=False)
        for matrix in self.filtered(
            lambda item: item.document_type == "hub_stock_request"
        ):
            lines = matrix.line_ids.sorted(lambda line: (line.sequence, line.id))
            seen_sequences = set()
            first_signature_seen = False
            for line in lines:
                if line.sequence in seen_sequences:
                    raise ValidationError(
                        _("HUB approval stages cannot use duplicate sequence numbers.")
                    )
                seen_sequences.add(line.sequence)
                if line.lhi_signature_required:
                    first_signature_seen = True
                elif first_signature_seen:
                    raise ValidationError(
                        _(
                            "Non-signature HUB review stages must occur before "
                            "the first LHI Sign stage."
                        )
                    )
            ned_lines = lines.filtered(lambda line: line.approver_group_id == ned)
            if ned_lines:
                director_lines = lines.filtered(
                    lambda line: line.approver_group_id == director
                )
                if not director_lines or min(director_lines.mapped("sequence")) >= min(
                    ned_lines.mapped("sequence")
                ):
                    raise ValidationError(
                        _(
                            "Director of Operations must approve before NED "
                            "whenever NED is in a HUB request route."
                        )
                    )

    def _lhi_matches_hub_request(self, request):
        self.ensure_one()
        if self.document_type != "hub_stock_request" or not self.active:
            return False
        if self.company_id != request.company_id:
            return False
        if self.currency_id != request.currency_id:
            return False
        if request.requested_operational_value < self.min_amount:
            return False
        if self.max_amount and request.requested_operational_value > self.max_amount:
            return False
        if (
            self.lhi_requesting_hub_ids
            and request.requesting_hub_id not in self.lhi_requesting_hub_ids
        ):
            return False
        if (
            self.lhi_supplying_hub_ids
            and request.supplying_hub_id not in self.lhi_supplying_hub_ids
        ):
            return False
        inter_state = (
            request.requesting_hub_id.lhi_state_id
            != request.supplying_hub_id.lhi_state_id
        )
        if self.lhi_inter_state == "yes" and not inter_state:
            return False
        if self.lhi_inter_state == "no" and inter_state:
            return False
        if self.lhi_priority not in (False, "any", request.priority):
            return False
        if self.lhi_emergency_rule == "only" and not request.emergency:
            return False
        if self.lhi_emergency_rule == "exclude" and request.emergency:
            return False
        products = request.line_ids.mapped("product_id")
        categories = products.mapped("categ_id")
        total_quantity = sum(request.line_ids.mapped("quantity_requested"))
        if total_quantity < self.lhi_min_quantity:
            return False
        if self.lhi_max_quantity and total_quantity > self.lhi_max_quantity:
            return False
        if (
            self.lhi_state_ids
            and request.requesting_hub_id.lhi_state_id not in self.lhi_state_ids
        ):
            return False
        if self.lhi_product_ids and not (products & self.lhi_product_ids):
            return False
        if self.lhi_item_category_ids and not (categories & self.lhi_item_category_ids):
            return False
        if self.lhi_requires_pharmaceuticals and not products.filtered(
            lambda product: product.lhi_hub_item_type == "pharmaceuticals"
        ):
            return False
        if self.lhi_requires_controlled_items and not products.filtered(
            "lhi_controlled_item"
        ):
            return False
        if self.lhi_requires_serialized and not products.filtered(
            lambda product: product.tracking == "serial"
        ):
            return False
        if self.lhi_requires_consignment_restriction and not request.line_ids.filtered(
            lambda line: line.selected_lot_id.lhi_consignment_id.usage_restrictions
        ):
            return False
        if self.project_ids and request.project_id not in self.project_ids:
            return False
        if (
            self.lhi_programme_ids
            and request.programme_id not in self.lhi_programme_ids
        ):
            return False
        if self.award_ids and request.award_id not in self.award_ids:
            return False
        if (
            self.lhi_donor_partner_ids
            and request.donor_id not in self.lhi_donor_partner_ids
        ):
            return False
        if self.lhi_effective_from and request.request_date < self.lhi_effective_from:
            return False
        if self.lhi_effective_to and request.request_date > self.lhi_effective_to:
            return False
        return True


class LhiApprovalMatrixLine(models.Model):
    _inherit = "lhi.approval.matrix.line"

    lhi_signature_required = fields.Boolean(string="LHI Sign Required", default=True)
    lhi_approval_role = fields.Selection(
        [
            ("group", "Security Group"),
            ("named", "Named User"),
            ("operations_manager", "Operations Manager"),
            ("director_operations", "Director of Operations"),
            ("ned", "National Executive Director"),
            ("programme", "Programme Approver"),
            ("project", "Project Approver"),
            ("donor_compliance", "Donor-compliance Reviewer"),
        ],
        default="group",
        required=True,
    )

    def _lhi_resolve_approver_users(self, request):
        users = super()._lhi_resolve_approver_users(request)
        self.ensure_one()
        if request.document_type != "hub_stock_request":
            return users
        source = self.env[request.res_model].browse(request.res_id).exists()
        if not source:
            return users
        if self.lhi_approval_role == "operations_manager":
            manager = source.supplying_hub_id.lhi_operations_manager_id
            if manager and manager in users:
                return manager
        if self.lhi_approval_role in ("operations_manager", "group"):
            authorized = (
                source.requesting_hub_id.lhi_authorized_user_ids
                | source.supplying_hub_id.lhi_authorized_user_ids
            )
            scoped = users & authorized
            if scoped:
                return scoped
        return users


class LhiApprovalRequest(models.Model):
    _inherit = "lhi.approval.request"

    document_type = fields.Selection(
        selection_add=[("hub_stock_request", "HUB Stock Request")],
        ondelete={"hub_stock_request": "cascade"},
    )
    lhi_hub_request_id = fields.Many2one(
        "lhi.hub.stock.request", readonly=True, copy=False, ondelete="cascade"
    )

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any(
                values.get("document_type") == "hub_stock_request"
                for values in vals_list
            )
            and self.env.context.get("lhi_hub_approval_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB approvals are created only by HUB requests."))
        return super().create(vals_list)

    def _lhi_assert_hub_source_decision(self):
        if (
            self.filtered(lambda request: request.document_type == "hub_stock_request")
            and self.env.context.get("lhi_hub_approval_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(
                _("Use the HUB Stock Request decision actions for this approval.")
            )

    def write(self, vals):
        protected = {"state", "matrix_id", "line_ids", "lhi_hub_request_id"}
        hub_requests = self.filtered(
            lambda request: request.document_type == "hub_stock_request"
        )
        if (
            hub_requests
            and protected.intersection(vals)
            and self.env.context.get("lhi_hub_approval_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(
                _("HUB approval state is controlled by its source workflow.")
            )
        return super().write(vals)

    def action_approve(self, notes=None):
        self._lhi_assert_hub_source_decision()
        return super().action_approve(notes=notes)

    def action_reject(self, notes=None):
        self._lhi_assert_hub_source_decision()
        return super().action_reject(notes=notes)

    def action_return_for_correction(self, notes=None):
        self._lhi_assert_hub_source_decision()
        return super().action_return_for_correction(notes=notes)


class LhiApprovalDelegation(models.Model):
    _inherit = "lhi.approval.delegation"

    document_type = fields.Selection(
        selection_add=[("hub_stock_request", "HUB Stock Request")],
        ondelete={"hub_stock_request": "cascade"},
    )


class LhiApprovalRequestLine(models.Model):
    _inherit = "lhi.approval.request.line"

    lhi_signature_required = fields.Boolean(readonly=True)
    lhi_approval_role = fields.Char(readonly=True)
    lhi_signer_name = fields.Char(readonly=True)
    lhi_signer_email = fields.Char(readonly=True)
    lhi_signed_at = fields.Datetime(readonly=True)
    lhi_provider_signer_id = fields.Char(readonly=True)
    lhi_provider_status = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        request_ids = [
            values.get("request_id") for values in vals_list if values.get("request_id")
        ]
        hub_requests = (
            self.env["lhi.approval.request"]
            .browse(request_ids)
            .filtered(lambda request: request.document_type == "hub_stock_request")
        )
        if (
            hub_requests
            and self.env.context.get("lhi_hub_approval_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB approval routes are workflow-generated."))
        return super().create(vals_list)

    def write(self, vals):
        protected = {
            "matrix_line_id",
            "name",
            "sequence",
            "approver_group_id",
            "approver_ids",
            "approved_user_ids",
            "approval_type",
            "timeout_days",
            "escalation_user_id",
            "state",
            "lhi_signature_required",
            "lhi_approval_role",
            "lhi_signer_name",
            "lhi_signer_email",
            "lhi_signed_at",
            "lhi_provider_signer_id",
            "lhi_provider_status",
        }
        hub_lines = self.filtered(
            lambda line: line.request_id.document_type == "hub_stock_request"
        )
        if (
            hub_lines
            and protected.intersection(vals)
            and self.env.context.get("lhi_hub_approval_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB approval route snapshots are immutable."))
        return super().write(vals)


class LhiApprovalHistory(models.Model):
    _inherit = "lhi.approval.history"

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("lhi_hub_approval_system") is not LHI_HUB_SYSTEM_TOKEN:
            line_ids = [
                values.get("request_line_id")
                for values in vals_list
                if values.get("request_line_id")
            ]
            hub_lines = (
                self.env["lhi.approval.request.line"]
                .browse(line_ids)
                .filtered(
                    lambda line: line.request_id.document_type == "hub_stock_request"
                )
            )
            if hub_lines:
                raise AccessError(
                    _("HUB approval history is provider/workflow-generated.")
                )
        return super().create(vals_list)


class LhiHubStockRequest(models.Model):
    _name = "lhi.hub.stock.request"
    _description = "LHI Internal HUB Stock Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "lhi.hub.access.mixin"]
    _order = "request_date desc, id desc"

    name = fields.Char(
        string="Request Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )
    requesting_hub_id = fields.Many2one("stock.warehouse", required=True, tracking=True)
    supplying_hub_id = fields.Many2one("stock.warehouse", required=True, tracking=True)
    request_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True
    )
    requested_by_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )
    project_id = fields.Many2one("lhi.project")
    programme_id = fields.Many2one("lhi.programme")
    award_id = fields.Many2one("lhi.award", string="Grant or Award")
    donor_id = fields.Many2one("res.partner")
    activity_id = fields.Many2one("lhi.workplan.activity")
    purpose = fields.Text(required=True)
    priority = fields.Selection(
        [
            ("routine", "Routine"),
            ("urgent", "Urgent"),
            ("critical", "Critical"),
        ],
        default="routine",
        required=True,
    )
    emergency = fields.Boolean()
    approval_matrix_id = fields.Many2one(
        "lhi.approval.matrix",
        required=True,
        domain="[('document_type', '=', 'hub_stock_request'), ('company_id', '=', company_id), ('active', '=', True)]",
    )
    approval_request_id = fields.Many2one(
        "lhi.approval.request", readonly=True, copy=False, ondelete="restrict"
    )
    current_approval_stage = fields.Char(compute="_compute_stages")
    current_signature_stage = fields.Char(compute="_compute_stages")
    line_ids = fields.One2many("lhi.hub.stock.request.line", "request_id", copy=True)
    total_operational_value = fields.Monetary(
        compute="_compute_total", store=True, currency_field="currency_id"
    )
    requested_operational_value = fields.Monetary(
        compute="_compute_total",
        store=True,
        currency_field="currency_id",
        help="Requested quantity value used to select the immutable approval route.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    quantities_locked = fields.Boolean(readonly=True, copy=False)
    quantities_locked_at = fields.Datetime(readonly=True, copy=False)
    quantities_locked_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    document_version_number = fields.Integer(default=1, required=True, copy=False)
    document_version_ids = fields.One2many(
        "lhi.hub.stock.request.document.version", "request_id", readonly=True
    )
    current_document_version_id = fields.Many2one(
        "lhi.hub.stock.request.document.version",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    opensign_request_id = fields.Many2one(
        "lhi.opensign.request",
        readonly=True,
        copy=False,
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    provider_request_id = fields.Char(readonly=True, copy=False)
    provider_status = fields.Char(readonly=True, copy=False)
    integration_error_code = fields.Char(readonly=True, copy=False)
    integration_error_message = fields.Text(readonly=True, copy=False)
    source_pdf_hash = fields.Char(readonly=True, copy=False)
    signed_pdf_hash = fields.Char(readonly=True, copy=False)
    audit_certificate_hash = fields.Char(readonly=True, copy=False)
    approval_completed_at = fields.Datetime(readonly=True, copy=False)
    reservation_picking_id = fields.Many2one(
        "stock.picking", readonly=True, copy=False, ondelete="restrict"
    )
    picking_ids = fields.One2many("stock.picking", "lhi_hub_request_id", readonly=True)
    close_unfulfilled_reason = fields.Text()
    supporting_document_ids = fields.Many2many(
        "ir.attachment",
        "lhi_hub_request_attachment_rel",
        "request_id",
        "attachment_id",
    )
    decision_reason = fields.Text(copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("quantity_review", "Quantity Review"),
            ("sign_preparation", "LHI Sign Preparation"),
            ("signing", "Approval and Signing"),
            ("approved", "Fully Signed and Approved"),
            ("reserved", "Stock Reserved"),
            ("partially_dispatched", "Partially Dispatched"),
            ("dispatched", "Dispatched"),
            ("in_transit", "In Transit"),
            ("partially_received", "Partially Received"),
            ("received", "Received"),
            ("closed", "Closed"),
            ("returned", "Returned for Correction"),
            ("rejected", "Rejected"),
            ("withdrawn", "Withdrawn"),
            ("integration_error", "Integration Error"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="requesting_hub_id.company_id", store=True, readonly=True
    )

    _request_name_company_unique = models.Constraint(
        "unique(name, company_id)", "HUB request numbers must be unique per company."
    )

    @api.depends(
        "line_ids.estimated_total_value",
        "line_ids.quantity_requested",
        "line_ids.operational_unit_value",
    )
    def _compute_total(self):
        for request in self:
            request.total_operational_value = sum(
                request.line_ids.mapped("estimated_total_value")
            )
            request.requested_operational_value = sum(
                line.quantity_requested * line.operational_unit_value
                for line in request.line_ids
            )

    @api.depends(
        "approval_request_id.current_line_id",
        "approval_request_id.current_line_id.name",
        "opensign_request_id.current_recipient_id",
    )
    def _compute_stages(self):
        for request in self:
            request.current_approval_stage = (
                request.approval_request_id.current_line_id.name or ""
            )
            recipient = request.sudo().opensign_request_id.current_recipient_id
            request.current_signature_stage = recipient.name if recipient else ""

    @api.constrains("requesting_hub_id", "supplying_hub_id")
    def _check_distinct_hubs(self):
        for request in self:
            if request.requesting_hub_id == request.supplying_hub_id:
                raise ValidationError(
                    _("Requesting and supplying HUBs must be different.")
                )
            if (
                request.requesting_hub_id.company_id
                != request.supplying_hub_id.company_id
            ):
                raise ValidationError(
                    _("Cross-company HUB requests are not supported.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                SYSTEM_REQUEST_FIELDS.intersection(vals)
                and self.env.context.get("lhi_hub_request_system")
                is not LHI_HUB_SYSTEM_TOKEN
            ):
                raise AccessError(
                    _("HUB request workflow and evidence fields are system-managed.")
                )
            if not self.env.user.has_group("lhi_security.group_lhi_erp_admin"):
                vals["requested_by_id"] = self.env.user.id
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "lhi.hub.stock.request"
                ) or _("New")
        return super().create(vals_list)

    def _lhi_assert_requester_access(self):
        self.ensure_one()
        if self.env.user.has_group("lhi_security.group_lhi_programme_user"):
            if (
                self.requested_by_id == self.env.user
                and self.requesting_hub_id in self.env.user.lhi_hub_ids
            ):
                return True
            raise AccessError(
                _("Programme users may act only on their own assigned-HUB requests.")
            )
        return self._lhi_assert_hub_access(self.requesting_hub_id)

    def write(self, vals):
        if (
            SYSTEM_REQUEST_FIELDS.intersection(vals)
            and self.env.context.get("lhi_hub_request_system")
            is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(
                _("HUB request workflow and evidence fields are system-managed.")
            )
        if MATERIAL_REQUEST_FIELDS.intersection(vals):
            locked = self.filtered(
                lambda request: (
                    request.state not in ("draft", "quantity_review", "returned")
                )
            )
            if locked:
                raise ValidationError(
                    _(
                        "Material HUB request fields are immutable after the "
                        "signature document is generated."
                    )
                )
        if "line_ids" in vals and any(request.quantities_locked for request in self):
            raise ValidationError(
                _("Approved quantities are locked. Return for correction first.")
            )
        return super().write(vals)

    def _lhi_approval_matrix_for_request(self, approval_request):
        self.ensure_one()
        if not self.approval_matrix_id._lhi_matches_hub_request(self):
            raise ValidationError(
                _("The selected approval matrix does not match this HUB request.")
            )
        return self.approval_matrix_id

    def _snapshot_request_line_route(self):
        self.ensure_one()
        for line in self.approval_request_id.line_ids:
            matrix_line = line.matrix_line_id
            values = {
                "lhi_signature_required": matrix_line.lhi_signature_required,
                "lhi_approval_role": matrix_line.lhi_approval_role,
            }
            if matrix_line.lhi_signature_required:
                if len(line.approver_ids) != 1:
                    raise ValidationError(
                        _(
                            "Signature stage '%s' must resolve to exactly one "
                            "active approver."
                        )
                        % line.name
                    )
                signer = line.approver_ids
                if not signer.email or not signer.entra_object_id:
                    raise ValidationError(
                        _(
                            "Signer %s requires an email address and synchronized "
                            "Microsoft Entra identity."
                        )
                        % signer.display_name
                    )
                values.update(
                    {
                        "lhi_signer_name": signer.name,
                        "lhi_signer_email": signer.email.strip().lower(),
                    }
                )
            line.sudo().with_context(
                lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
            ).write(values)

    def action_submit(self):
        for request in self:
            request._lhi_assert_requester_access()
            if request.state not in ("draft", "returned"):
                raise UserError(_("Only draft or returned requests can be submitted."))
            if not request.line_ids:
                raise ValidationError(_("Add at least one requested item."))
            if not request.approval_matrix_id._lhi_matches_hub_request(request):
                raise ValidationError(
                    _("The selected approval matrix does not match this request.")
                )
            if request.approval_request_id:
                approval = request.approval_request_id
                approval.with_context(
                    lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
                ).action_prepare()
            else:
                approval = (
                    self.env["lhi.approval.request"]
                    .with_context(lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN)
                    .create(
                        {
                            "res_model": request._name,
                            "res_id": request.id,
                            "document_type": "hub_stock_request",
                            "amount": request.requested_operational_value,
                            "currency_id": request.currency_id.id,
                            "creator_id": request.requested_by_id.id,
                            "office_id": request.requesting_hub_id.lhi_office_id.id,
                            "project_id": request.project_id.id,
                            "award_id": request.award_id.id,
                            "company_id": request.company_id.id,
                            "lhi_hub_request_id": request.id,
                        }
                    )
                )
                request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                    {"approval_request_id": approval.id}
                )
                approval.with_context(
                    lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
                ).action_prepare()
            request._snapshot_request_line_route()
            request.line_ids.with_context(
                lhi_hub_line_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "supplying_hub_confirmed": False,
                    "quantity_available": 0.0,
                }
            )
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {
                    "state": "quantity_review",
                    "quantities_locked": False,
                    "integration_error_code": False,
                    "integration_error_message": False,
                }
            )
            request._lhi_notify(
                "request_submitted",
                _("HUB stock request %s was submitted.") % request.name,
                request.requested_by_id
                | request.requesting_hub_id.lhi_operations_manager_id
                | request.supplying_hub_id.lhi_operations_manager_id,
            )
            request._lhi_notify(
                "quantity_review",
                _("Quantity review required for %s.") % request.name,
                request.supplying_hub_id.lhi_warehouse_officer_ids
                | request.supplying_hub_id.lhi_operations_officer_ids,
            )
        return True

    def action_review_availability(self):
        for request in self:
            request._lhi_assert_hub_access(request.supplying_hub_id)
            if request.state != "quantity_review" or request.quantities_locked:
                raise UserError(_("This request is not open for quantity review."))
            for line in request.line_ids:
                lot = line.selected_lot_id
                if lot:
                    lot._lhi_assert_issuable()
                available = self.env["stock.quant"]._get_available_quantity(
                    line.product_id,
                    request.supplying_hub_id.lot_stock_id,
                    lot_id=lot,
                    strict=False,
                )
                line.with_context(lhi_hub_line_system=LHI_HUB_SYSTEM_TOKEN).write(
                    {
                        "quantity_available": max(available, 0.0),
                        "supplying_hub_confirmed": True,
                    }
                )
        return True

    def _render_request_pdf(self):
        self.ensure_one()
        content, _content_type = self.env["ir.actions.report"]._render_qweb_pdf(
            "lhi_hub_management.action_report_hub_stock_request",
            res_ids=[self.id],
        )
        if not content.startswith(b"%PDF"):
            raise ValidationError(
                _("The HUB Stock Request report did not render a PDF.")
            )
        return content

    def _signature_recipient_commands(self):
        self.ensure_one()
        commands = []
        signature_lines = self.approval_request_id.line_ids.filtered(
            "lhi_signature_required"
        ).sorted("sequence")
        for index, line in enumerate(signature_lines, start=1):
            user = line.approver_ids
            commands.append(
                (
                    0,
                    0,
                    {
                        "sequence": index * 10,
                        "user_id": user.id,
                        "name": user.name,
                        "email": user.email.strip().lower(),
                        "entra_tenant_id": user.entra_tenant_id,
                        "entra_object_id": user.entra_object_id,
                        "participant_role": (
                            "final_signer"
                            if index == len(signature_lines)
                            else "approver"
                        ),
                        "provider_role": "signer",
                        "required_widget_types": "signature,name,date",
                    },
                )
            )
        if not commands:
            raise ValidationError(
                _("The HUB approval route must contain at least one signature stage.")
            )
        return commands

    def action_lock_quantities_and_generate(self):
        version_model = self.env["lhi.hub.stock.request.document.version"]
        for request in self:
            request._lhi_assert_hub_access(request.supplying_hub_id)
            if request.state != "quantity_review" or request.quantities_locked:
                raise UserError(_("This request is not ready to lock quantities."))
            approved_total = 0.0
            for line in request.line_ids:
                line._lhi_validate_review()
                approved_total += line.quantity_approved
            if approved_total <= 0:
                raise ValidationError(
                    _("Approve a positive quantity on at least one line.")
                )
            request.approval_request_id.with_context(
                lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
            ).action_activate()
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {
                    "quantities_locked": True,
                    "quantities_locked_at": fields.Datetime.now(),
                    "quantities_locked_by_id": self.env.user.id,
                }
            )
            pdf_content = request._render_request_pdf()
            source_hash = hashlib.sha256(pdf_content).hexdigest()
            idempotency_key = (
                f"lhi-hub-request-{request.id}-v"
                f"{request.document_version_number}-{source_hash}"
            )
            existing = (
                self.env["lhi.opensign.request"]
                .sudo()
                .search([("idempotency_key", "=", idempotency_key)], limit=1)
            )
            if existing:
                raise ValidationError(
                    _(
                        "This immutable document version already has an LHI Sign "
                        "request. Reconcile it instead of creating another."
                    )
                )
            version = version_model.with_context(
                lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
            ).create(
                {
                    "request_id": request.id,
                    "version": request.document_version_number,
                    "previous_version_id": request.current_document_version_id.id,
                    "source_pdf_hash": source_hash,
                    "change_reason": (
                        _("Initial approved quantity document")
                        if request.document_version_number == 1
                        else _("Corrected HUB Stock Request")
                    ),
                    "changed_by_id": self.env.user.id,
                }
            )
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {
                    "current_document_version_id": version.id,
                    "source_pdf_hash": source_hash,
                }
            )
            signatories = [
                {
                    "name": command[2]["name"],
                    "email": command[2]["email"],
                    "role": request.approval_request_id.line_ids.filtered(
                        lambda line: line.lhi_signer_email == command[2]["email"]
                    )[:1].lhi_approval_role,
                }
                for command in request._signature_recipient_commands()
            ]
            opensign = (
                self.env["lhi.opensign.request"]
                .sudo()
                .create(
                    {
                        "name": f"{request.name}-V{request.document_version_number}",
                        "res_model": request._name,
                        "res_id": request.id,
                        "company_id": request.company_id.id,
                        "source_pdf": base64.b64encode(pdf_content),
                        "source_pdf_name": (
                            f"LHI-HUB-REQUEST-{request.name}-"
                            f"V{request.document_version_number}-Submitted.pdf"
                        ),
                        "source_pdf_hash": source_hash,
                        "signatories": json.dumps({"signatories": signatories}),
                        "recipient_ids": request._signature_recipient_commands(),
                        "sequence_type": "sequential",
                        "idempotency_key": idempotency_key,
                    }
                )
            )
            version.sudo().with_context(
                lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "source_document_item_id": opensign.source_document_item_id.id,
                    "source_sharepoint_item_id": (
                        opensign.source_document_item_id.sharepoint_item_id
                    ),
                    "source_file_size": opensign.source_document_item_id.file_size,
                    "opensign_request_id": opensign.id,
                    "provider_request_id": opensign.provider_request_id,
                    "state": "source_stored",
                }
            )
            request.sudo().with_context(
                lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN
            ).write(
                {
                    "opensign_request_id": opensign.id,
                    "provider_status": opensign.status,
                    "state": "sign_preparation",
                }
            )
            request._lhi_notify(
                "sign_preparation",
                _("LHI Sign preparation required for %s.") % request.name,
                request.supplying_hub_id.lhi_warehouse_officer_ids
                | request.supplying_hub_id.lhi_operations_manager_id,
            )
        return True

    def _lhi_opensign_storage_target(self, field_name, suffix):
        self.ensure_one()
        version = self.current_document_version_id
        if not version:
            raise ValidationError(
                _("No immutable HUB request document version exists.")
            )
        suffix_by_field = {
            "source_pdf": "Submitted",
            "signed_pdf": "Signed",
            "audit_certificate": "Audit-Certificate",
        }
        return {
            "linked_model": version._name,
            "linked_record_id": version.id,
            "linked_field": field_name,
            "requested_by": self.requested_by_id,
            "name": (
                f"LHI-HUB-REQUEST-{self.name}-V{version.version}-"
                f"{suffix_by_field.get(field_name, suffix)}.pdf"
            ),
        }

    def action_create_lhi_sign_draft(self):
        self.ensure_one()
        self._lhi_assert_hub_access(self.supplying_hub_id)
        if self.state not in ("sign_preparation", "integration_error"):
            raise UserError(_("This request is not awaiting LHI Sign preparation."))
        try:
            url = self.sudo().opensign_request_id.action_create_provider_draft()
        except Exception:
            return self._lhi_record_integration_failure("provider_draft_failed")
        opensign = self.sudo().opensign_request_id
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "provider_request_id": opensign.provider_request_id,
                "provider_status": opensign.provider_status or opensign.status,
                "state": "sign_preparation",
                "integration_error_code": False,
                "integration_error_message": opensign.error_message,
            }
        )
        self.current_document_version_id.with_context(
            lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
        ).write(
            {
                "provider_request_id": opensign.provider_request_id,
                "state": "provider_draft",
            }
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_confirm_lhi_sign_preparation(self):
        self.ensure_one()
        self._lhi_assert_hub_access(self.supplying_hub_id)
        if self.state not in ("sign_preparation", "integration_error"):
            raise UserError(_("This request is not awaiting field preparation."))
        try:
            self.sudo().opensign_request_id.action_confirm_preparation()
        except Exception:
            return self._lhi_record_integration_failure("preparation_failed")
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "state": "signing",
                "provider_status": self.sudo().opensign_request_id.status,
                "integration_error_code": False,
                "integration_error_message": False,
            }
        )
        self.current_document_version_id.with_context(
            lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
        ).write({"state": "signing"})
        self._lhi_notify_current_approver()
        return True

    def action_approve_non_signature_stage(self, notes=None):
        self.ensure_one()
        line = self.approval_request_id._lhi_assert_current_approver()
        if line.lhi_signature_required:
            raise UserError(_("Use Approve and Sign for this approval stage."))
        self.approval_request_id.with_context(
            lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
        ).action_approve(notes=notes)
        self._lhi_notify_current_approver()
        return True

    def action_approve_and_sign(self):
        self.ensure_one()
        if self.state != "signing" or not self.quantities_locked:
            raise UserError(_("The immutable request is not ready for signing."))
        line = self.approval_request_id._lhi_assert_current_approver()
        if not line.lhi_signature_required:
            raise UserError(_("This stage does not require an LHI Sign signature."))
        opensign = self.sudo().opensign_request_id
        recipient = opensign.recipient_ids.filtered(
            lambda item: item.user_id == self.env.user
        )[:1]
        if not recipient or recipient != opensign.current_recipient_id:
            raise AccessError(_("You are not the current LHI Sign participant."))
        url = opensign.signing_url_for_user(self.env.user)
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def opensign_event_hook(self, request_id, event_type, payload):
        self.ensure_one()
        opensign = self.sudo().opensign_request_id
        if opensign.id != request_id:
            raise ValidationError(
                _("The LHI Sign request does not match this version.")
            )
        if event_type != "signed":
            if event_type in ("declined", "revoked"):
                self.sudo().with_context(
                    lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN
                ).write(
                    {
                        "state": "rejected",
                        "provider_status": event_type,
                    }
                )
                self._lhi_notify(
                    "request_rejected",
                    _("LHI Sign reported %s for HUB request %s.")
                    % (event_type, self.name),
                    self.requested_by_id,
                )
            return True
        email = (
            (
                ((payload.get("signer") or {}).get("email"))
                or payload.get("viewedBy")
                or ""
            )
            .strip()
            .lower()
        )
        recipient = opensign.recipient_ids.filtered(
            lambda item: item.email.strip().lower() == email
        )[:1]
        if not recipient or not recipient.user_id:
            raise ValidationError(
                _("The confirmed signer is not in the route snapshot.")
            )
        current_line = self.approval_request_id.current_line_id
        if not current_line or current_line.lhi_signer_email.strip().lower() != email:
            raise ValidationError(_("The provider signer is out of approval sequence."))
        signed_line = current_line
        self.approval_request_id.with_user(recipient.user_id).with_context(
            lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
        ).action_approve(notes=_("Confirmed by authenticated LHI Sign provider event."))
        signed_line.sudo().with_context(
            lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
        ).write(
            {
                "lhi_signed_at": recipient.completed_at or fields.Datetime.now(),
                "lhi_provider_signer_id": str(recipient.id),
                "lhi_provider_status": "signed",
            }
        )
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {"provider_status": opensign.provider_status or opensign.status}
        )
        self._lhi_notify_current_approver()
        return True

    def opensign_completed_hook(self, request_id):
        self.ensure_one()
        opensign = self.sudo().opensign_request_id
        if opensign.id != request_id:
            raise ValidationError(_("The completed LHI Sign request is not current."))
        if self.approval_request_id.state != "approved":
            raise ValidationError(
                _("LHI Sign completed before the snapshotted approval route.")
            )
        if not (opensign.signed_stored and opensign.certificate_stored):
            raise ValidationError(
                _("Signed PDF and audit certificate must be verified in SharePoint.")
            )
        version = self.current_document_version_id
        version.sudo().with_context(lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "signed_document_item_id": opensign.signed_document_item_id.id,
                "certificate_document_item_id": (
                    opensign.certificate_document_item_id.id
                ),
                "signed_pdf_hash": opensign.signed_pdf_hash,
                "audit_certificate_hash": (
                    opensign.certificate_document_item_id.checksum
                ),
                "approval_completed_at": fields.Datetime.now(),
                "signed_sharepoint_item_id": (
                    opensign.signed_document_item_id.sharepoint_item_id
                ),
                "certificate_sharepoint_item_id": (
                    opensign.certificate_document_item_id.sharepoint_item_id
                ),
                "state": "completed",
            }
        )
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "state": "approved",
                "provider_status": "completed",
                "signed_pdf_hash": opensign.signed_pdf_hash,
                "audit_certificate_hash": (
                    opensign.certificate_document_item_id.checksum
                ),
                "integration_error_code": False,
                "integration_error_message": False,
            }
        )
        self._lhi_notify(
            "route_completed",
            _("HUB request %s is fully signed and ready for reservation.") % self.name,
            self.supplying_hub_id.lhi_warehouse_officer_ids,
        )
        self._lhi_notify(
            "request_approved",
            _("HUB request %s was approved and fully signed.") % self.name,
            self.requested_by_id | self.requesting_hub_id.lhi_operations_manager_id,
        )
        self._lhi_notify(
            "stock_ready_for_reservation",
            _("Stock for %s is ready for reservation.") % self.name,
            self.supplying_hub_id.lhi_warehouse_officer_ids
            | self.supplying_hub_id.lhi_operations_officer_ids,
        )
        return True

    def action_refresh_lhi_sign_status(self):
        self.ensure_one()
        self._lhi_assert_any_hub_access(self.requesting_hub_id | self.supplying_hub_id)
        opensign = self.sudo().opensign_request_id
        if not opensign:
            raise UserError(_("No LHI Sign request exists."))
        try:
            opensign.action_reconcile()
        except Exception:
            return self._lhi_record_integration_failure("reconciliation_failed")
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "provider_status": opensign.provider_status or opensign.status,
                "integration_error_code": False,
                "integration_error_message": opensign.error_message,
            }
        )
        return True

    def _lhi_record_integration_failure(self, code):
        """Persist a redacted, retryable failure without rolling back audit state."""
        self.ensure_one()
        message = _(
            "The LHI Sign operation did not complete. No approval or stock "
            "movement was advanced. An administrator can inspect the integration "
            "diagnostics and retry this request."
        )
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "state": "integration_error",
                "integration_error_code": code,
                "integration_error_message": message,
            }
        )
        if self.current_document_version_id:
            self.current_document_version_id.sudo().with_context(
                lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"state": "failed"})
        self.message_post(body=message)
        self._lhi_notify(
            "integration_failure",
            _("%s has an LHI Sign integration failure.") % self.name,
            self.supplying_hub_id.lhi_operations_manager_id,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("LHI Sign operation failed safely"),
                "message": message,
                "type": "warning",
                "sticky": True,
            },
        }

    def action_return_for_correction(self, reason=None):
        self.ensure_one()
        reason = reason or self.decision_reason
        if not (reason or "").strip():
            raise ValidationError(_("A correction reason is required."))
        self.approval_request_id._lhi_assert_current_approver()
        opensign = self.sudo().opensign_request_id
        if opensign:
            opensign.action_cancel()
        self.approval_request_id.with_context(
            lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
        ).action_return_for_correction(notes=reason)
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "state": "returned",
                "quantities_locked": False,
                "document_version_number": self.document_version_number + 1,
                "provider_status": "superseded",
                "decision_reason": False,
            }
        )
        self.current_document_version_id.with_context(
            lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
        ).write({"state": "superseded", "change_reason": reason})
        self._lhi_notify(
            "request_returned",
            _("HUB request %(request)s was returned for correction: %(reason)s")
            % {"request": self.name, "reason": reason},
            self.requested_by_id,
        )
        return True

    def action_reject(self, reason=None):
        self.ensure_one()
        reason = reason or self.decision_reason
        if not (reason or "").strip():
            raise ValidationError(_("A rejection reason is required."))
        self.approval_request_id._lhi_assert_current_approver()
        if self.sudo().opensign_request_id:
            self.sudo().opensign_request_id.action_cancel()
        self.approval_request_id.with_context(
            lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN
        ).action_reject(notes=reason)
        self.sudo().with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
            {
                "state": "rejected",
                "provider_status": "revoked",
                "decision_reason": False,
            }
        )
        self._lhi_notify(
            "request_rejected",
            _("HUB request %(request)s was rejected: %(reason)s")
            % {"request": self.name, "reason": reason},
            self.requested_by_id,
        )
        return True

    def action_withdraw(self):
        for request in self:
            if (
                request.requested_by_id != self.env.user
                and not self.env.user.has_group(
                    "lhi_security.group_lhi_operations_manager"
                )
                and not self.env.user.has_group("lhi_security.group_lhi_erp_admin")
            ):
                raise AccessError(
                    _("Only the requester or Operations Manager may withdraw.")
                )
            if request.state in (
                "approved",
                "reserved",
                "partially_dispatched",
                "dispatched",
                "in_transit",
                "partially_received",
                "received",
                "closed",
            ):
                raise UserError(_("This request can no longer be withdrawn."))
            current_approvers = (
                request.approval_request_id.current_line_id.approver_ids
                if request.approval_request_id
                else self.env["res.users"]
            )
            opensign = request.sudo().opensign_request_id
            if opensign:
                opensign.action_cancel()
                if opensign.status != "cancelled":
                    raise UserError(_("LHI Sign revocation was not confirmed."))
            request.sudo().with_context(
                lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN
            ).write({"state": "withdrawn", "provider_status": "revoked"})
            request._lhi_notify(
                "request_withdrawn",
                _("HUB request %s was withdrawn; no approval action is required.")
                % request.name,
                current_approvers,
            )
        return True

    def action_reserve_stock(self):
        stock_service = self.env["lhi.hub.stock.service"]
        for request in self:
            request._lhi_assert_hub_access(request.supplying_hub_id)
            if request.state not in ("approved", "partially_dispatched"):
                raise UserError(_("Only fully signed requests can reserve stock."))
            opensign = request.sudo().opensign_request_id
            if (
                not opensign
                or opensign.status != "completed"
                or not opensign.signed_stored
                or not opensign.certificate_stored
            ):
                raise ValidationError(
                    _(
                        "Stock reservation is blocked until all LHI Sign artefacts are verified."
                    )
                )
            if (
                request.reservation_picking_id
                and request.reservation_picking_id.state
                not in (
                    "done",
                    "cancel",
                )
            ):
                raise ValidationError(
                    _("This request already has an active reservation.")
                )
            specs = []
            for line in request.line_ids:
                outstanding = line.quantity_approved - line.quantity_dispatched
                if outstanding > 0:
                    specs.append(
                        {
                            "product": line.product_id,
                            "quantity": outstanding,
                            "uom": line.uom_id,
                            "lot": line.selected_lot_id,
                            "values": {
                                "lhi_hub_request_line_id": line.id,
                                "lhi_project_id": request.project_id.id,
                                "lhi_donor_id": request.donor_id.id,
                                "lhi_activity_id": request.activity_id.id,
                            },
                        }
                    )
            picking = stock_service._lhi_create_picking(
                picking_type=request.supplying_hub_id.out_type_id,
                source_location=request.supplying_hub_id.lot_stock_id,
                destination_location=request.company_id.internal_transit_location_id,
                origin=request.name,
                move_specs=specs,
                picking_values={
                    "lhi_hub_request_id": request.id,
                    "lhi_hub_document_type": "request_dispatch",
                    "lhi_project_id": request.project_id.id,
                    "lhi_donor_id": request.donor_id.id,
                },
                reserve=True,
            )
            for move in picking.move_ids:
                move.lhi_hub_request_line_id.sudo().with_context(
                    lhi_hub_line_system=LHI_HUB_SYSTEM_TOKEN
                ).write({"quantity_reserved": move.quantity})
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"reservation_picking_id": picking.id, "state": "reserved"}
            )
        return True

    def action_dispatch(self):
        stock_service = self.env["lhi.hub.stock.service"]
        for request in self:
            request._lhi_assert_hub_access(request.supplying_hub_id)
            picking = request.reservation_picking_id
            if request.state != "reserved" or not picking:
                raise UserError(_("Reserve stock before dispatch."))
            dispatched_any = False
            for move in picking.move_ids:
                line = move.lhi_hub_request_line_id
                quantity = line.quantity_to_dispatch or move.product_uom_qty
                if quantity <= 0 or quantity > move.product_uom_qty:
                    raise ValidationError(
                        _("Invalid dispatch quantity for %s.")
                        % line.product_id.display_name
                    )
                move.product_uom_qty = quantity
                if move.product_uom.compare(move.quantity, quantity) < 0:
                    raise ValidationError(_("Reserved stock is no longer available."))
                move.quantity = quantity
                line.sudo().with_context(
                    lhi_hub_line_system=LHI_HUB_SYSTEM_TOKEN
                ).write(
                    {
                        "quantity_dispatched": line.quantity_dispatched + quantity,
                        "quantity_reserved": 0.0,
                        "quantity_to_dispatch": 0.0,
                    }
                )
                dispatched_any = True
            if not dispatched_any:
                raise ValidationError(_("Enter a positive dispatch quantity."))
            stock_service._lhi_validate_picking(picking)
            outstanding = sum(
                request.line_ids.mapped(
                    lambda line: line.quantity_approved - line.quantity_dispatched
                )
            )
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {
                    "reservation_picking_id": False,
                    "state": "partially_dispatched"
                    if outstanding > 0
                    else "in_transit",
                }
            )
            request._lhi_store_report_artifact(
                "dispatch_note",
                "lhi_hub_management.action_report_hub_dispatch_note",
                picking.name,
            )
            request._lhi_notify(
                "stock_dispatched",
                _("Stock for HUB request %s was dispatched.") % request.name,
                request.requested_by_id
                | request.requesting_hub_id.lhi_warehouse_officer_ids
                | request.requesting_hub_id.lhi_operations_officer_ids,
            )
            if outstanding > 0:
                request._lhi_notify(
                    "partial_fulfilment",
                    _("HUB request %s was partially dispatched.") % request.name,
                    request.requested_by_id
                    | request.requesting_hub_id.lhi_operations_manager_id
                    | request.supplying_hub_id.lhi_operations_manager_id,
                )
        return True

    def action_receive(self):
        stock_service = self.env["lhi.hub.stock.service"]
        for request in self:
            request._lhi_assert_hub_access(request.requesting_hub_id)
            if request.state not in (
                "partially_dispatched",
                "in_transit",
                "partially_received",
            ):
                raise UserError(_("No dispatched stock is awaiting receipt."))
            specs = []
            for line in request.line_ids:
                awaiting = line.quantity_dispatched - line.quantity_received
                quantity = line.quantity_to_receive or awaiting
                if quantity < 0 or quantity > awaiting:
                    raise ValidationError(
                        _("Invalid receipt quantity for %s.")
                        % line.product_id.display_name
                    )
                if quantity:
                    specs.append(
                        {
                            "product": line.product_id,
                            "quantity": quantity,
                            "uom": line.uom_id,
                            "lot": line.selected_lot_id,
                            "values": {
                                "lhi_hub_request_line_id": line.id,
                                "lhi_project_id": request.project_id.id,
                                "lhi_donor_id": request.donor_id.id,
                            },
                        }
                    )
            picking = stock_service._lhi_create_picking(
                picking_type=request.requesting_hub_id.in_type_id,
                source_location=request.company_id.internal_transit_location_id,
                destination_location=request.requesting_hub_id.lot_stock_id,
                origin=request.name,
                move_specs=specs,
                picking_values={
                    "lhi_hub_request_id": request.id,
                    "lhi_hub_document_type": "request_receipt",
                    "lhi_project_id": request.project_id.id,
                    "lhi_donor_id": request.donor_id.id,
                },
                reserve=True,
            )
            for move in picking.move_ids:
                line = move.lhi_hub_request_line_id
                line.sudo().with_context(
                    lhi_hub_line_system=LHI_HUB_SYSTEM_TOKEN
                ).write(
                    {
                        "quantity_received": line.quantity_received
                        + move.product_uom_qty,
                        "quantity_to_receive": 0.0,
                    }
                )
            stock_service._lhi_validate_picking(picking)
            remaining_receipt = sum(
                request.line_ids.mapped(
                    lambda line: line.quantity_dispatched - line.quantity_received
                )
            )
            remaining_dispatch = sum(
                request.line_ids.mapped(
                    lambda line: line.quantity_approved - line.quantity_dispatched
                )
            )
            state = (
                "received"
                if not remaining_receipt and not remaining_dispatch
                else "partially_received"
            )
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": state}
            )
            request._lhi_store_report_artifact(
                "receipt_confirmation",
                "lhi_hub_management.action_report_hub_goods_receipt",
                picking.name,
            )
            request._lhi_notify(
                "stock_received",
                _("Stock for HUB request %s was received.") % request.name,
                request.requested_by_id
                | request.supplying_hub_id.lhi_warehouse_officer_ids
                | request.supplying_hub_id.lhi_operations_officer_ids,
            )
            if state == "partially_received":
                request._lhi_notify(
                    "partial_fulfilment",
                    _("HUB request %s remains partially fulfilled after receipt.")
                    % request.name,
                    request.requested_by_id
                    | request.requesting_hub_id.lhi_operations_manager_id
                    | request.supplying_hub_id.lhi_operations_manager_id,
                )
        return True

    def action_close(self):
        for request in self:
            request._lhi_assert_any_hub_access(
                request.requesting_hub_id | request.supplying_hub_id
            )
            if request.state not in (
                "received",
                "partially_received",
                "partially_dispatched",
            ):
                raise UserError(_("This request is not ready to close."))
            outstanding = sum(
                request.line_ids.mapped(
                    lambda line: max(
                        line.quantity_approved - line.quantity_received, 0.0
                    )
                )
            )
            if outstanding and not (request.close_unfulfilled_reason or "").strip():
                raise ValidationError(
                    _("An unfulfilled-balance reason is required before closure.")
                )
            request.with_context(lhi_hub_request_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"state": "closed"}
            )
        return True

    def _lhi_store_report_artifact(self, artifact_type, report_xmlid, reference):
        self.ensure_one()
        content, _content_type = self.env["ir.actions.report"]._render_qweb_pdf(
            report_xmlid, res_ids=[self.id]
        )
        if not content.startswith(b"%PDF"):
            raise ValidationError(_("The operational document did not render as PDF."))
        filename = f"{self.name}-{artifact_type}-{reference}.pdf".replace("/", "-")
        document = self.env["lhi.document.item"].create_from_bytes(
            name=filename,
            content=content,
            mime_type="application/pdf",
            linked_model=self._name,
            linked_record_id=self.id,
            linked_field=artifact_type,
            requested_by=self.env.user,
            synchronous=True,
        )
        self.env["lhi.hub.stock.request.artifact"].sudo().with_context(
            lhi_hub_artifact_system=LHI_HUB_SYSTEM_TOKEN
        ).create(
            {
                "request_id": self.id,
                "artifact_type": artifact_type,
                "document_item_id": document.id,
                "filename": document.name,
                "sharepoint_item_id": document.sharepoint_item_id,
                "checksum": document.checksum,
                "file_size": document.file_size,
            }
        )
        return document

    def _lhi_notify(self, event_type, message, users):
        self.ensure_one()
        return self.env["lhi.hub.notification"].enqueue(
            source=self,
            event_type=event_type,
            message=message,
            users=users,
        )

    def _lhi_notify_current_approver(self):
        self.ensure_one()
        line = self.approval_request_id.current_line_id
        if not line:
            return self.env["lhi.hub.notification"]
        signature_required = bool(line.lhi_signature_required)
        return self._lhi_notify(
            (
                "approval_signature_required"
                if signature_required
                else "approval_required"
            ),
            (
                _("Approval and signature workflow context is ready for %s.")
                if signature_required
                else _("Approval workflow action is required for %s.")
            )
            % self.name,
            line.approver_ids,
        )

    def unlink(self):
        if any(request.state != "draft" for request in self):
            raise ValidationError(_("Submitted HUB requests cannot be deleted."))
        return super().unlink()


class LhiHubStockRequestLine(models.Model):
    _name = "lhi.hub.stock.request.line"
    _description = "LHI HUB Stock Request Line"
    _order = "id"

    request_id = fields.Many2one(
        "lhi.hub.stock.request", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        string="Item Description",
        required=True,
        domain="[('is_storable', '=', True), ('lhi_hub_item_type', '!=', False)]",
    )
    item_description = fields.Char(required=True)
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure", required=True)
    quantity_requested = fields.Float(required=True)
    quantity_available = fields.Float(readonly=True)
    quantity_recommended = fields.Float()
    quantity_approved = fields.Float()
    purpose_remarks = fields.Text(string="Purpose / Remarks", required=True)
    stock_availability_remarks = fields.Text()
    partial_fulfilment_reason = fields.Text()
    alternative_product_id = fields.Many2one("product.product")
    expected_fulfilment_date = fields.Date()
    supplying_hub_confirmed = fields.Boolean(readonly=True)
    operational_unit_value = fields.Monetary(
        required=True, currency_field="currency_id"
    )
    estimated_total_value = fields.Monetary(
        compute="_compute_estimated_total", store=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(related="request_id.currency_id", store=True)
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, readonly=True
    )
    selected_lot_id = fields.Many2one(
        "stock.lot",
        domain="[('product_id', '=', product_id), ('lhi_quarantine_status', '=', 'released')]",
    )
    quantity_reserved = fields.Float(readonly=True)
    quantity_dispatched = fields.Float(readonly=True)
    quantity_received = fields.Float(readonly=True)
    outstanding_quantity = fields.Float(compute="_compute_outstanding")
    quantity_to_dispatch = fields.Float()
    quantity_to_receive = fields.Float()

    @api.depends("quantity_approved", "operational_unit_value")
    def _compute_estimated_total(self):
        for line in self:
            line.estimated_total_value = (
                line.quantity_approved * line.operational_unit_value
            )

    @api.depends("quantity_approved", "quantity_received")
    def _compute_outstanding(self):
        for line in self:
            line.outstanding_quantity = max(
                line.quantity_approved - line.quantity_received, 0.0
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.item_description = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            self.operational_unit_value = self.product_id.lhi_operational_unit_value

    @api.model_create_multi
    def create(self, vals_list):
        system_fields = {
            "quantity_available",
            "supplying_hub_confirmed",
            "quantity_reserved",
            "quantity_dispatched",
            "quantity_received",
        }
        for vals in vals_list:
            if (
                system_fields.intersection(vals)
                and self.env.context.get("lhi_hub_line_system")
                is not LHI_HUB_SYSTEM_TOKEN
            ):
                raise AccessError(
                    _("HUB stock quantities are updated only by workflows.")
                )
            request = self.env["lhi.hub.stock.request"].browse(vals.get("request_id"))
            if request.exists():
                request._lhi_assert_requester_access()
                if request.state not in ("draft", "returned"):
                    raise AccessError(
                        _("Lines can be added only to draft or returned requests.")
                    )
        return super().create(vals_list)

    @api.constrains(
        "quantity_requested",
        "quantity_recommended",
        "quantity_approved",
        "quantity_dispatched",
        "quantity_received",
    )
    def _check_quantities(self):
        for line in self:
            if line.quantity_requested <= 0:
                raise ValidationError(_("Requested quantity must be positive."))
            if (
                min(
                    line.quantity_recommended,
                    line.quantity_approved,
                    line.quantity_dispatched,
                    line.quantity_received,
                )
                < 0
            ):
                raise ValidationError(_("HUB request quantities cannot be negative."))
            if line.quantity_approved > line.quantity_requested:
                raise ValidationError(
                    _("Approved quantity cannot exceed requested quantity.")
                )
            if line.quantity_dispatched > line.quantity_approved:
                raise ValidationError(
                    _("Dispatched quantity cannot exceed approved quantity.")
                )
            if line.quantity_received > line.quantity_dispatched:
                raise ValidationError(
                    _("Received quantity cannot exceed dispatched quantity.")
                )

    def _lhi_validate_review(self):
        self.ensure_one()
        if not self.supplying_hub_confirmed:
            raise ValidationError(
                _("Supplying HUB confirmation is required for every line.")
            )
        if self.quantity_approved > self.quantity_requested:
            raise ValidationError(
                _("Approved quantity exceeds requested quantity for %s.")
                % self.product_id.display_name
            )
        if self.quantity_approved > self.quantity_available:
            raise ValidationError(
                _("Approved quantity exceeds available stock for %s.")
                % self.product_id.display_name
            )
        if (
            self.quantity_approved < self.quantity_requested
            and not (self.partial_fulfilment_reason or "").strip()
        ):
            raise ValidationError(
                _("A partial-fulfilment reason is required for %s.")
                % self.product_id.display_name
            )
        if self.product_id.tracking != "none" and not self.selected_lot_id:
            raise ValidationError(
                _("Select a valid lot or serial for tracked item %s.")
                % self.product_id.display_name
            )
        if self.selected_lot_id:
            self.selected_lot_id._lhi_assert_issuable()
        return True

    def write(self, vals):
        identity_fields = {
            "product_id",
            "item_description",
            "uom_id",
            "quantity_requested",
            "purpose_remarks",
            "operational_unit_value",
        }
        if identity_fields.intersection(vals) and any(
            line.request_id.state not in ("draft", "returned") for line in self
        ):
            raise ValidationError(
                _("Submitted item identity and requested quantities are immutable.")
            )
        controlled_review_fields = {
            "quantity_approved",
            "selected_lot_id",
            "quantity_recommended",
            "partial_fulfilment_reason",
            "stock_availability_remarks",
            "alternative_product_id",
            "expected_fulfilment_date",
        }
        system_fields = {
            "quantity_available",
            "supplying_hub_confirmed",
            "quantity_reserved",
            "quantity_dispatched",
            "quantity_received",
        }
        if (
            system_fields.intersection(vals)
            and self.env.context.get("lhi_hub_line_system") is not LHI_HUB_SYSTEM_TOKEN
        ):
            raise AccessError(_("HUB stock quantities are updated only by workflows."))
        if identity_fields.intersection(vals):
            for line in self:
                line.request_id._lhi_assert_requester_access()
        if controlled_review_fields.intersection(vals):
            for line in self:
                line.request_id._lhi_assert_hub_access(line.request_id.supplying_hub_id)
        if "quantity_to_dispatch" in vals:
            for line in self:
                line.request_id._lhi_assert_hub_access(line.request_id.supplying_hub_id)
        if "quantity_to_receive" in vals:
            for line in self:
                line.request_id._lhi_assert_hub_access(
                    line.request_id.requesting_hub_id
                )
        if controlled_review_fields.intersection(vals) and any(
            line.request_id.quantities_locked for line in self
        ):
            raise ValidationError(
                _("Approved request lines are locked. Return for correction first.")
            )
        return super().write(vals)

    def unlink(self):
        if any(line.request_id.state != "draft" for line in self):
            raise ValidationError(_("Submitted HUB request lines cannot be deleted."))
        return super().unlink()


class LhiHubStockRequestDocumentVersion(models.Model):
    _name = "lhi.hub.stock.request.document.version"
    _description = "Immutable HUB Stock Request Document Version"
    _order = "request_id, version desc"

    request_id = fields.Many2one(
        "lhi.hub.stock.request", required=True, ondelete="cascade", index=True
    )
    version = fields.Integer(required=True)
    previous_version_id = fields.Many2one(
        "lhi.hub.stock.request.document.version", ondelete="restrict"
    )
    superseding_version_id = fields.Many2one(
        "lhi.hub.stock.request.document.version", ondelete="restrict"
    )
    change_reason = fields.Text(required=True)
    changed_by_id = fields.Many2one("res.users", required=True)
    changed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    opensign_request_id = fields.Many2one(
        "lhi.opensign.request",
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    provider_request_id = fields.Char(readonly=True)
    source_pdf_hash = fields.Char(required=True, readonly=True)
    signed_pdf_hash = fields.Char(readonly=True)
    audit_certificate_hash = fields.Char(readonly=True)
    source_document_item_id = fields.Many2one(
        "lhi.document.item",
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    signed_document_item_id = fields.Many2one(
        "lhi.document.item",
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    certificate_document_item_id = fields.Many2one(
        "lhi.document.item",
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    source_sharepoint_item_id = fields.Char(readonly=True)
    signed_sharepoint_item_id = fields.Char(readonly=True)
    certificate_sharepoint_item_id = fields.Char(readonly=True)
    source_file_size = fields.Integer(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("source_stored", "Source Stored"),
            ("provider_draft", "Provider Draft"),
            ("signing", "Signing"),
            ("completed", "Completed"),
            ("superseded", "Superseded"),
            ("revoked", "Revoked"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, readonly=True
    )

    _request_version_unique = models.Constraint(
        "unique(request_id, version)",
        "HUB request document version numbers must be unique.",
    )
    _request_hash_unique = models.Constraint(
        "unique(request_id, source_pdf_hash)",
        "The same immutable HUB request PDF cannot be versioned twice.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("lhi_hub_version_system") is not LHI_HUB_SYSTEM_TOKEN:
            raise AccessError(
                _("HUB request document versions are workflow-generated.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("lhi_hub_version_system") is not LHI_HUB_SYSTEM_TOKEN:
            raise AccessError(_("HUB request document versions are immutable."))
        result = super().write(vals)
        for version in self:
            if version.previous_version_id:
                version.previous_version_id.with_context(
                    lhi_hub_version_system=LHI_HUB_SYSTEM_TOKEN
                ).write({"superseding_version_id": version.id})
        return result

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise AccessError(_("HUB request document versions are immutable."))
        return super().unlink()


class LhiHubStockRequestArtifact(models.Model):
    _name = "lhi.hub.stock.request.artifact"
    _description = "HUB Stock Request SharePoint Artifact"
    _order = "create_date desc, id desc"

    request_id = fields.Many2one(
        "lhi.hub.stock.request", required=True, ondelete="cascade", index=True
    )
    artifact_type = fields.Selection(
        [
            ("dispatch_note", "Dispatch Note"),
            ("receipt_confirmation", "Receipt Confirmation"),
        ],
        required=True,
    )
    document_item_id = fields.Many2one(
        "lhi.document.item",
        required=True,
        ondelete="restrict",
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    filename = fields.Char(required=True, readonly=True)
    sharepoint_item_id = fields.Char(required=True, readonly=True)
    checksum = fields.Char(required=True, readonly=True)
    file_size = fields.Integer(required=True, readonly=True)
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("lhi_hub_artifact_system") is not LHI_HUB_SYSTEM_TOKEN:
            raise AccessError(
                _("HUB request artifacts are created only after SharePoint storage.")
            )
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Stored HUB request artifacts are immutable."))

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise AccessError(_("Stored HUB request artifacts are immutable."))
        return super().unlink()
