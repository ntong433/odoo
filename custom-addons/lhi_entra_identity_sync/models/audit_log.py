from odoo import fields, models


class LhiAuditLog(models.Model):
    _inherit = "lhi.audit.log"

    event_type = fields.Selection(
        selection_add=[
            ("identity_sync", "Entra Identity Synchronization"),
            ("identity_rollback", "Entra Identity Rollback"),
            ("maintenance_login", "Maintenance Administrator Login"),
        ],
        ondelete={
            "identity_sync": "cascade",
            "identity_rollback": "cascade",
            "maintenance_login": "cascade",
        },
    )
