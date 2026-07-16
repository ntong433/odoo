from odoo import fields, models


class LhiGraphDiagnostic(models.Model):
    _name = "lhi.graph.diagnostic"
    _description = "Microsoft Graph Diagnostic Run"
    _order = "create_date desc, id desc"

    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="connection_id.company_id",
        store=True,
        index=True,
    )
    run_by_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="restrict",
    )
    state = fields.Selection(
        [("success", "Success"), ("failure", "Failure")],
        required=True,
        index=True,
    )
    completed_at = fields.Datetime(required=True)
    details = fields.Text(
        readonly=True,
        help="Structured safe diagnostic results. Tokens, credentials, and payloads are excluded.",
    )

