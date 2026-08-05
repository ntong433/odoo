from odoo import http, fields, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


class LhiSharePointDocumentController(http.Controller):
    @http.route(
        "/lhi/sharepoint/document/<string:document_uuid>/download",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def download_document(self, document_uuid, **kwargs):
        document = request.env["lhi.document.item"].sudo().search(
            [("uuid", "=", document_uuid)], limit=1
        )
        if not document or not document.linked_model or not document.linked_record_id:
            return request.not_found()
        linked_record = request.env[document.linked_model].browse(document.linked_record_id).exists()
        if not linked_record:
            return request.not_found()
        try:
            linked_record.check_access("read")
        except AccessError:
            return request.not_found()

        try:
            content = document.sudo().download_bytes(auth_context="application")
        except (AccessError, UserError, ValidationError):
            return request.not_found()

        filename = document.name or "document"
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        mime_type = document.mime_type or "application/octet-stream"
        is_pdf = mime_type == "application/pdf" or filename.lower().endswith(".pdf")
        disposition = f"inline; filename=\"{filename}\"" if is_pdf else f"attachment; filename=\"{filename}\""

        headers = [
            ("Content-Type", mime_type),
            ("Content-Length", str(len(content))),
            ("Content-Disposition", disposition),
            ("Cache-Control", "private, no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        return request.make_response(content, headers=headers)

    @http.route(
        "/lhi/sharepoint/upload/session",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def create_upload_session(
        self, model, record_id, field_name, name, size, mime_type, checksum=False
    ):
        record = request.env[model].browse(int(record_id)).exists()
        if not record:
            raise ValidationError(_("Save the business record before adding documents."))
        record.check_access("write")
        field = record._fields.get(field_name)
        if not field or field.comodel_name != "ir.attachment":
            raise ValidationError(_("The requested document field is invalid."))
        if not record._has_field_access(field, "write"):
            raise AccessError(_("You cannot upload to this document field."))
        company = (
            record.company_id
            if "company_id" in record._fields and record.company_id
            else request.env.user.company_id
        )
        policy = request.env["lhi.document.storage.policy"].resolve_policy(
            model, field_name, company
        )
        if (
            not policy
            or policy.storage_backend != "sharepoint"
            or not policy.direct_browser_upload
        ):
            raise ValidationError(_("Direct SharePoint upload is not enabled here."))
        size = int(size)
        policy.validate_file(name, size)
        connection = request.env["lhi.graph.connection"].sudo()._get_active_connection(company)
        project, award, grant = request.env["lhi.document.item"]._business_links(record)
        item = request.env["lhi.document.item"].sudo().create(
            {
                "name": name,
                "mime_type": mime_type or "application/octet-stream",
                "file_size": size,
                "checksum": checksum or False,
                "company_id": company.id,
                "requested_by_id": request.env.user.id,
                "graph_connection_id": connection.id,
                "storage_policy_id": policy.id,
                "linked_model": model,
                "linked_record_id": record.id,
                "linked_field": field_name,
                "linked_record_uuid": (
                    record.uuid
                    if "uuid" in record._fields and record.uuid
                    else f"{model}:{record.id}"
                ),
                "project_id": project.id if project else False,
                "award_id": award.id if award else False,
                "grant_reference": grant,
                "document_category": policy.document_category,
                "confidentiality": policy.confidentiality,
                "workflow_state": (
                    str(record.state)
                    if "state" in record._fields and record.state
                    else False
                ),
                "retention_category": policy.retention_category,
                "idempotency_key": (
                    f"browser:{request.env.cr.dbname}:{request.env.user.id}:"
                    f"{model}:{record.id}:{field_name}:{fields.Datetime.now()}:{name}"
                ),
                "storage_state": "uploading",
                "upload_state": "session",
            }
        )
        library = connection.lhi_get_library(policy.library_code)
        item._ensure_project_template(library, "delegated", request.env.user)
        parent_id = connection.lhi_ensure_folder_path(
            library,
            item._folder_path(),
            auth_context="delegated",
            user=request.env.user,
        )
        session = connection.lhi_create_upload_session(
            library,
            parent_id,
            name,
            conflict_behavior=policy.conflict_behavior,
            auth_context="delegated",
            user=request.env.user,
        )
        item.sudo().write(
            {
                "sharepoint_drive_id": library.drive_id,
                "sharepoint_parent_item_id": parent_id,
                "upload_url": session["uploadUrl"],
                "upload_session_expiration": item._parse_graph_datetime(
                    session.get("expirationDateTime")
                ),
            }
        )
        return {
            "document_uuid": item.uuid,
            "upload_url": session["uploadUrl"],
            "chunk_size": policy.upload_chunk_size_kb * 1024,
        }

    @http.route(
        "/lhi/sharepoint/upload/confirm",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def confirm_upload(self, document_uuid, item_id):
        document = request.env["lhi.document.item"].sudo().search(
            [
                ("uuid", "=", document_uuid),
                ("requested_by_id", "=", request.env.user.id),
                ("upload_state", "in", ("session", "uploading")),
            ],
            limit=1,
        )
        if not document:
            raise AccessError(_("The upload session is invalid or has expired."))
        document.with_user(request.env.user).check_linked_access("write")
        payload = document.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{document.sharepoint_drive_id}/items/{item_id}"
                "?$select=id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,"
                "lastModifiedBy,parentReference,file"
            ),
            auth_context="delegated",
            user=request.env.user,
        )
        parent = payload.get("parentReference") or {}
        if (
            payload.get("id") != item_id
            or parent.get("driveId") != document.sharepoint_drive_id
            or parent.get("id") != document.sharepoint_parent_item_id
            or int(payload.get("size") or -1) != document.file_size
        ):
            raise ValidationError(_("The completed SharePoint upload could not be verified."))
        document._apply_drive_item(payload)
        document.sudo().write({"upload_state": "verifying"})
        document._calculate_remote_hashes(
            auth_context="delegated", user=request.env.user
        )
        document._patch_sharepoint_metadata(
            auth_context="delegated", user=request.env.user
        )
        document._verify_drive_item(
            auth_context="delegated", user=request.env.user
        )
        attachment = request.env["ir.attachment"].with_context(
            lhi_sharepoint_skip_adapter=True
        ).create(
            {
                "name": document.name,
                "type": "binary",
                "mimetype": document.mime_type,
                "res_model": document.linked_model,
                "res_id": document.linked_record_id,
                "res_field": document.linked_field,
                "lhi_document_item_id": document.id,
            }
        )
        document.sudo().write(
            {
                "storage_state": "available",
                "upload_state": "completed",
                "reconciliation_state": "matched",
                "upload_url": False,
                "upload_session_expiration": False,
                "last_error": False,
            }
        )
        document.message_post(body=_("Browser upload confirmed by SharePoint."))
        return {
            "attachment_id": attachment.id,
            "name": attachment.name,
            "mimetype": attachment.mimetype,
        }

    @http.route(
        "/lhi/sharepoint/attachment/remove",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
    )
    def remove_attachment(self, attachment_id):
        attachment = request.env["ir.attachment"].browse(int(attachment_id)).exists()
        if not attachment:
            return True
        attachment.check_access("write")
        document = attachment.lhi_document_item_id
        if document:
            document.with_user(request.env.user).action_archive_remote()
        attachment.with_context(lhi_sharepoint_skip_adapter=True).unlink()
        return True
