from odoo import fields, models


class LhiAuditLog(models.Model):
    _inherit = "lhi.audit.log"

    event_type = fields.Selection(
        selection_add=[
            ("document_preview", "Document Preview"),
            ("document_edit", "Document Edit"),
            ("document_download", "Document Download"),
            ("document_version", "Document Version Change"),
            ("document_archive", "Document Archive"),
            ("document_create", "Document Created from Template"),
            ("document_link_copy", "Governed Document Link Copied"),
        ],
        ondelete={
            "document_preview": "cascade",
            "document_edit": "cascade",
            "document_download": "cascade",
            "document_version": "cascade",
            "document_archive": "cascade",
            "document_create": "cascade",
            "document_link_copy": "cascade",
        },
    )

