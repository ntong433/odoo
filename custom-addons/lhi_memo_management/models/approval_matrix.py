from odoo import fields, models


class LhiApprovalMatrix(models.Model):
    _inherit = "lhi.approval.matrix"

    document_type = fields.Selection(
        selection_add=[("memo", "Memo")], ondelete={"memo": "cascade"}
    )


class LhiApprovalRequest(models.Model):
    _inherit = "lhi.approval.request"

    document_type = fields.Selection(
        selection_add=[("memo", "Memo")], ondelete={"memo": "cascade"}
    )


class LhiApprovalDelegation(models.Model):
    _inherit = "lhi.approval.delegation"

    document_type = fields.Selection(
        selection_add=[("memo", "Memo")], ondelete={"memo": "cascade"}
    )
