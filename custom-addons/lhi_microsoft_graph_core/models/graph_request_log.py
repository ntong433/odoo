from odoo import fields, models


class LhiGraphRequestLog(models.Model):
    _name = "lhi.graph.request.log"
    _description = "Microsoft Graph Structured Request Log"
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
    user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    auth_context = fields.Selection(
        [("application", "Application"), ("delegated", "Delegated")],
        required=True,
        index=True,
    )
    method = fields.Char(required=True, index=True)
    resource_path = fields.Char(required=True)
    outcome = fields.Selection(
        [("success", "Success"), ("retry", "Retry"), ("failure", "Failure")],
        required=True,
        index=True,
    )
    status_code = fields.Integer(index=True)
    duration_ms = fields.Integer()
    retry_count = fields.Integer()
    client_request_id = fields.Char(index=True)
    graph_request_id = fields.Char(index=True)
    error_code = fields.Char(index=True)
    safe_message = fields.Text()

