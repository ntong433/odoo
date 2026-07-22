from odoo import fields, models


class LhiOpenSignRecipient(models.Model):
    _name = "lhi.opensign.recipient"
    _description = "LHI Sign Request Recipient"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "lhi.opensign.request", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="request_id.company_id", store=True, readonly=True, index=True
    )
    sequence = fields.Integer(required=True, default=10)
    user_id = fields.Many2one("res.users", ondelete="restrict", index=True)
    name = fields.Char(required=True)
    email = fields.Char(required=True, index=True)
    entra_tenant_id = fields.Char(readonly=True, index=True)
    entra_object_id = fields.Char(readonly=True, index=True)
    participant_role = fields.Selection(
        [
            ("requester", "Requester"),
            ("approver", "Approver"),
            ("final_signer", "Final Signer"),
            ("viewer", "Viewer"),
        ],
        required=True,
    )
    provider_role = fields.Selection(
        [("signer", "Signer"), ("approver", "Approver"), ("viewer", "Viewer")],
        required=True,
    )
    required_widget_types = fields.Char(readonly=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("viewed", "Viewed"),
            ("completed", "Completed"),
            ("declined", "Declined"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    viewed_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    decline_reason = fields.Text(readonly=True)
    provider_signing_url = fields.Char(
        readonly=True, groups="lhi_signature_bridge.group_lhi_signature_admin"
    )

    _request_sequence_unique = models.Constraint(
        "unique(request_id, sequence)",
        "Each signature recipient must have a unique request sequence.",
    )
