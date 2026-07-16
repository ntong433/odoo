from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    lhi_graph_connection_id = fields.Many2one(
        "lhi.graph.connection",
        string="Microsoft Graph Connection",
        compute="_compute_lhi_graph_connection_id",
    )

    def _compute_lhi_graph_connection_id(self):
        for settings in self:
            settings.lhi_graph_connection_id = self.env[
                "lhi.graph.connection"
            ].sudo().search(
                [
                    ("active", "=", True),
                    ("company_id", "=", settings.company_id.id),
                ],
                order="id",
                limit=1,
            )

    def action_open_lhi_graph_connections(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Microsoft Graph Connections",
            "res_model": "lhi.graph.connection",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.env.company.id)],
            "context": {"default_company_id": self.env.company.id},
        }

