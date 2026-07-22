from odoo import fields, models


class LhiOpenSignRequest(models.Model):
    _inherit = "lhi.opensign.request"

    memo_id = fields.Many2one(
        "lhi.memo", readonly=True, copy=False, ondelete="restrict", index=True
    )
