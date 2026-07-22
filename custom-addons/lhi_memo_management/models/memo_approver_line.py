from odoo import fields, models


class LhiMemoApproverLine(models.Model):
    _name = "lhi.memo.approver.line"
    _description = "LHI Memo Approval Participant"
    _order = "sequence, id"

    memo_id = fields.Many2one("lhi.memo", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        related="memo_id.company_id", store=True, readonly=True, index=True
    )
    cycle_number = fields.Integer(required=True, default=1, readonly=True, index=True)
    sequence = fields.Integer(required=True, index=True)
    stage_name = fields.Char(required=True)
    approver_user_id = fields.Many2one(
        "res.users", required=True, ondelete="restrict", index=True
    )
    approval_request_line_id = fields.Many2one(
        "lhi.approval.request.line", required=True, ondelete="restrict", index=True
    )
    signature_recipient_id = fields.Many2one(
        "lhi.opensign.recipient", readonly=True, ondelete="set null", index=True
    )
    participant_role = fields.Selection(
        [("approver", "Approver"), ("final_signer", "Final Signer")],
        required=True,
        default="approver",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("returned", "Returned"),
            ("rejected", "Rejected"),
            ("superseded", "Superseded"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    acted_at = fields.Datetime(readonly=True)
    comments = fields.Text(readonly=True)

    _memo_sequence_unique = models.Constraint(
        "unique(memo_id, cycle_number, sequence)",
        "Each memo approval participant must have a unique sequence per cycle.",
    )
