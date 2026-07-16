from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = "res.users"

    lhi_graph_delegated_authorized = fields.Boolean(
        string="Microsoft Graph Authorized",
        compute="_compute_lhi_graph_delegated_status",
    )
    lhi_graph_delegated_expires_at = fields.Datetime(
        string="Microsoft Graph Token Expires",
        compute="_compute_lhi_graph_delegated_status",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "lhi_graph_delegated_authorized",
            "lhi_graph_delegated_expires_at",
        ]

    @api.depends_context("uid", "company")
    def _compute_lhi_graph_delegated_status(self):
        connection_model = self.env["lhi.graph.connection"]
        for user in self:
            connection = connection_model.sudo().search(
                [
                    ("active", "=", True),
                    ("company_id", "=", user.company_id.id),
                    ("delegated_permission_mode", "=", "sites_selected"),
                ],
                order="id",
                limit=1,
            )
            token = self.env["lhi.graph.token"].sudo().search(
                [
                    (
                        "cache_key",
                        "=",
                        f"delegated:{connection.id}:{user.id}" if connection else "none",
                    )
                ],
                limit=1,
            )
            user.lhi_graph_delegated_authorized = bool(
                token and token.refresh_token
            )
            user.lhi_graph_delegated_expires_at = token.expires_at if token else False

    def _check_graph_self_or_admin(self):
        self.ensure_one()
        if self != self.env.user and not self.env.user.has_group(
            "lhi_security.group_lhi_erp_admin"
        ):
            raise AccessError(_("You can manage only your own Microsoft Graph authorization."))

    def action_lhi_graph_authorize(self):
        self._check_graph_self_or_admin()
        connection = self.env["lhi.graph.connection"]._get_active_connection(
            company=self.company_id
        )
        return connection.delegated_authorization_action(self)

    def action_lhi_graph_revoke(self):
        self._check_graph_self_or_admin()
        connections = self.env["lhi.graph.connection"].sudo().search(
            [("company_id", "=", self.company_id.id)]
        )
        keys = [f"delegated:{connection.id}:{self.id}" for connection in connections]
        if keys:
            self.env["lhi.graph.token"].sudo().search(
                [("cache_key", "in", keys)]
            ).unlink()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Microsoft Graph"),
                "message": _("Delegated Microsoft Graph tokens were removed from Odoo."),
                "type": "success",
                "sticky": False,
            },
        }

