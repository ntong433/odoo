# -*- coding: utf-8 -*-
from odoo import fields, models


class LhiApprovalMatrix(models.Model):
    _inherit = "lhi.approval.matrix"

    document_type = fields.Selection(
        selection_add=[
            ("asset_transfer", "Asset Transfer"),
            ("asset_disposal", "Asset Disposal"),
        ],
        ondelete={
            "asset_transfer": "cascade",
            "asset_disposal": "cascade",
        },
    )


class LhiApprovalRequest(models.Model):
    _inherit = "lhi.approval.request"

    document_type = fields.Selection(
        selection_add=[
            ("asset_transfer", "Asset Transfer"),
            ("asset_disposal", "Asset Disposal"),
        ],
        ondelete={
            "asset_transfer": "cascade",
            "asset_disposal": "cascade",
        },
    )


class LhiApprovalDelegation(models.Model):
    _inherit = "lhi.approval.delegation"

    document_type = fields.Selection(
        selection_add=[
            ("asset_transfer", "Asset Transfer"),
            ("asset_disposal", "Asset Disposal"),
        ],
        ondelete={
            "asset_transfer": "cascade",
            "asset_disposal": "cascade",
        },
    )
