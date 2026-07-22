from datetime import date

from odoo import models


class LhiDocumentItem(models.Model):
    _inherit = "lhi.document.item"

    def _folder_path(self):
        self.ensure_one()
        if self.linked_model != "lhi.memo":
            return super()._folder_path()
        memo = self.env["lhi.memo"].browse(self.linked_record_id).exists()
        if not memo:
            return super()._folder_path()
        year = (memo.draft_date or date.today()).year
        department = memo.department_id.code or memo.department_id.name or "General"
        safe_department = self.graph_connection_id._lhi_safe_segment(department)
        safe_reference = self.graph_connection_id._lhi_safe_segment(
            (memo.name or f"Memo-{memo.id}").replace("/", "-")
        )
        return f"Memos/{year}/{safe_department}/{safe_reference}"
