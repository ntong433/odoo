import base64

from odoo import api, fields, models
from odoo.http import Stream
from odoo.tools import human_size


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    lhi_document_item_id = fields.Many2one(
        "lhi.document.item",
        string="SharePoint Document",
        ondelete="restrict",
        index=True,
        copy=False,
    )
    lhi_storage_state = fields.Selection(
        related="lhi_document_item_id.storage_state", readonly=True
    )
    lhi_remote_file_size = fields.Integer(
        string="SharePoint File Size",
        related="lhi_document_item_id.file_size",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        original_values = [dict(values) for values in vals_list]
        records = super().create(vals_list)
        if self.env.context.get("lhi_sharepoint_skip_adapter"):
            return records
        for attachment, original in zip(records, original_values):
            if attachment.type != "binary" or not attachment.res_model or not attachment.res_id:
                continue
            policy = self.env["lhi.document.storage.policy"].resolve_policy(
                attachment.res_model,
                attachment.res_field or False,
                self.env.company,
            )
            if not policy or policy.storage_backend != "sharepoint":
                continue
            raw = original.get("raw")
            if raw is None and original.get("datas"):
                raw = base64.b64decode(original["datas"])
            if isinstance(raw, str):
                raw = raw.encode()
            if not raw:
                continue
            self.env["lhi.document.item"].create_from_bytes(
                name=attachment.name,
                content=raw,
                mime_type=attachment.mimetype,
                linked_model=attachment.res_model,
                linked_record_id=attachment.res_id,
                linked_field=attachment.res_field or False,
                policy=policy,
                requested_by=self.env.user,
                attachment=attachment,
                synchronous=len(raw) <= policy.small_upload_limit_mb * 1024 * 1024,
            )
        return records

    def write(self, vals):
        if self.env.context.get("lhi_sharepoint_skip_adapter"):
            return super().write(vals)
        raw = vals.get("raw")
        if raw is None and vals.get("datas"):
            raw = base64.b64decode(vals["datas"])
        if isinstance(raw, str):
            raw = raw.encode()
        result = super().write(vals)
        if raw:
            for attachment in self:
                policy = self.env["lhi.document.storage.policy"].resolve_policy(
                    attachment.res_model,
                    attachment.res_field or False,
                    self.env.company,
                )
                if not policy or policy.storage_backend != "sharepoint":
                    continue
                old_item = attachment.lhi_document_item_id
                item = self.env["lhi.document.item"].create_from_bytes(
                    name=attachment.name,
                    content=raw,
                    mime_type=attachment.mimetype,
                    linked_model=attachment.res_model,
                    linked_record_id=attachment.res_id,
                    linked_field=attachment.res_field or False,
                    policy=policy,
                    requested_by=self.env.user,
                    attachment=attachment,
                    synchronous=len(raw)
                    <= policy.small_upload_limit_mb * 1024 * 1024,
                )
                if old_item and old_item != item:
                    old_item.sudo().write({"active": False, "storage_state": "archived"})
        return result

    @api.depends("store_fname", "db_datas", "lhi_document_item_id.storage_state")
    def _compute_raw(self):
        local = self.filtered(lambda item: not item.lhi_document_item_id)
        if local:
            super(IrAttachment, local)._compute_raw()
        for attachment in self - local:
            if attachment.lhi_document_item_id.storage_state == "available":
                auth_context = self.env.context.get("lhi_sharepoint_auth_context")
                if not auth_context:
                    auth_context = "application" if self.env.su else "delegated"
                attachment.raw = attachment.lhi_document_item_id.download_bytes(
                    auth_context=auth_context,
                    user=self.env.user,
                )
            else:
                attachment.raw = b""

    @api.depends(
        "store_fname",
        "db_datas",
        "file_size",
        "lhi_document_item_id.file_size",
        "lhi_document_item_id.storage_state",
    )
    @api.depends_context("bin_size")
    def _compute_datas(self):
        local = self.filtered(lambda item: not item.lhi_document_item_id)
        if local:
            super(IrAttachment, local)._compute_datas()
        for attachment in self - local:
            if self.env.context.get("bin_size"):
                attachment.datas = human_size(
                    attachment.lhi_document_item_id.file_size
                )
            else:
                attachment.datas = base64.b64encode(attachment.raw or b"")

    def _to_http_stream(self):
        self.ensure_one()
        if not self.lhi_document_item_id:
            return super()._to_http_stream()
        return Stream(
            type="url",
            url=f"/lhi/sharepoint/document/{self.lhi_document_item_id.uuid}/download",
            mimetype=self.mimetype,
            download_name=self.name,
            etag=self.lhi_document_item_id.sharepoint_etag
            or self.lhi_document_item_id.checksum,
            size=self.lhi_document_item_id.file_size,
            max_age=0,
            public=False,
        )

    def unlink(self):
        if not self.env.context.get("lhi_sharepoint_skip_adapter"):
            documents = self.mapped("lhi_document_item_id").filtered(
                lambda item: item.storage_state not in ("archived", "deleted")
            )
            if documents:
                documents.action_archive_remote()
        return super().unlink()
