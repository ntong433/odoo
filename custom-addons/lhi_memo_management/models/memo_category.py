from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LhiMemoCategory(models.Model):
    _name = "lhi.memo.category"
    _description = "LHI Memo Category"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    approval_matrix_id = fields.Many2one(
        "lhi.approval.matrix",
        string="Default Approval Route",
        domain="[('document_type', '=', 'memo'), ('active', '=', True), ('company_id', '=', company_id)]",
        ondelete="restrict",
    )
    default_recipient_ids = fields.Many2many("res.users", string="Default Recipients")
    approval_threshold = fields.Monetary(currency_field="currency_id", default=0)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )
    final_signature_required = fields.Boolean(default=True)
    requester_signature_required = fields.Boolean(default=True)
    default_expiry_days = fields.Integer(default=15, required=True)
    starter_document_item_id = fields.Many2one(
        "lhi.document.item",
        string="Approved Word Starter Document",
        domain="[('storage_state', '=', 'available'), ('mime_type', '=', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')]",
        ondelete="restrict",
    )

    _code_company_unique = models.Constraint(
        "unique(code, company_id)", "The memo category code must be unique per company."
    )

    @api.constrains("default_expiry_days", "approval_threshold")
    def _check_values(self):
        for category in self:
            if not 1 <= category.default_expiry_days <= 365:
                raise ValidationError(_("Memo expiry must be between 1 and 365 days."))
            if category.approval_threshold < 0:
                raise ValidationError(
                    _("The memo approval threshold cannot be negative.")
                )

    @api.constrains("starter_document_item_id")
    def _check_starter_document(self):
        expected = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        for category in self.filtered("starter_document_item_id"):
            item = category.starter_document_item_id
            if item.storage_state != "available" or item.mime_type != expected:
                raise ValidationError(
                    _("The memo starter must be an available SharePoint Word document.")
                )

    @api.constrains(
        "company_id",
        "approval_matrix_id",
        "starter_document_item_id",
        "default_recipient_ids",
    )
    def _check_company_scope(self):
        for category in self:
            for record in (
                category.approval_matrix_id,
                category.starter_document_item_id,
            ):
                if (
                    category.company_id
                    and record
                    and "company_id" in record._fields
                    and record.company_id
                    and record.company_id != category.company_id
                ):
                    raise ValidationError(
                        _("Memo category references must belong to the same company.")
                    )
            if category.company_id and category.default_recipient_ids.filtered(
                lambda user: category.company_id not in user.company_ids
            ):
                raise ValidationError(
                    _(
                        "Default memo recipients must be authorized for the category company."
                    )
                )
