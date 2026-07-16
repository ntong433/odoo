from odoo import fields, models


class LhiGraphToken(models.Model):
    _name = "lhi.graph.token"
    _description = "Protected Microsoft Graph Token Cache"
    _order = "expires_at desc, id desc"

    cache_key = fields.Char(required=True, index=True, groups=fields.NO_ACCESS)
    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        ondelete="cascade",
        groups=fields.NO_ACCESS,
    )
    user_id = fields.Many2one(
        "res.users",
        ondelete="cascade",
        groups=fields.NO_ACCESS,
    )
    token_context = fields.Selection(
        [("application", "Application"), ("delegated", "Delegated")],
        required=True,
        groups=fields.NO_ACCESS,
    )
    access_token = fields.Text(
        copy=False,
        prefetch=False,
        groups=fields.NO_ACCESS,
    )
    refresh_token = fields.Text(
        copy=False,
        prefetch=False,
        groups=fields.NO_ACCESS,
    )
    token_type = fields.Char(groups=fields.NO_ACCESS)
    scope = fields.Text(groups=fields.NO_ACCESS)
    expires_at = fields.Datetime(required=True, index=True, groups=fields.NO_ACCESS)

    _cache_key_unique = models.Constraint(
        "unique(cache_key)",
        "A Microsoft Graph token cache key must be unique.",
    )

