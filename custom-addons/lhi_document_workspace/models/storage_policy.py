from odoo import fields, models


class LhiDocumentStoragePolicy(models.Model):
    _inherit = "lhi.document.storage.policy"

    workspace_enabled = fields.Boolean(
        default=True,
        help="Expose policy-backed documents in native LHI document workspaces.",
    )
    workspace_lock_states = fields.Char(
        default="locked,done,cancel,cancelled,closed,completed,signed,archived",
        help=(
            "Comma-separated linked-record states that prevent edit, replacement, "
            "new-version, and archive actions. Read and preview remain available."
        ),
    )

