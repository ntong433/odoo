from datetime import timedelta

from odoo import api, fields, models


class LhiGraphOAuthState(models.Model):
    _name = "lhi.graph.oauth.state"
    _description = "Protected Microsoft Graph OAuth State"
    _order = "create_date desc"

    nonce = fields.Char(required=True, index=True, groups=fields.NO_ACCESS)
    connection_id = fields.Many2one(
        "lhi.graph.connection",
        required=True,
        ondelete="cascade",
        groups=fields.NO_ACCESS,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="cascade",
        groups=fields.NO_ACCESS,
    )
    code_verifier = fields.Char(
        required=True,
        copy=False,
        prefetch=False,
        groups=fields.NO_ACCESS,
    )
    expires_at = fields.Datetime(required=True, index=True, groups=fields.NO_ACCESS)
    used = fields.Boolean(default=False, groups=fields.NO_ACCESS)

    _nonce_unique = models.Constraint(
        "unique(nonce)",
        "A Microsoft Graph OAuth nonce must be unique.",
    )

    @api.autovacuum
    def _gc_expired_states(self):
        cutoff = fields.Datetime.now()
        self.sudo().search(
            ["|", ("expires_at", "<", cutoff), ("used", "=", True)],
            limit=1000,
        ).unlink()

    @api.model
    def _cron_cleanup(self):
        self._gc_expired_states()
        log_cutoff = fields.Datetime.now() - timedelta(days=90)
        self.env["lhi.graph.request.log"].sudo().search(
            [("create_date", "<", log_cutoff)],
            limit=5000,
        ).unlink()
        return True

