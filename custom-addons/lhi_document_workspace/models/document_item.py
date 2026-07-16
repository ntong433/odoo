import hashlib
import json
import os
from collections import defaultdict
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


OFFICE_SCHEMES = {
    "word": "ms-word",
    "excel": "ms-excel",
    "powerpoint": "ms-powerpoint",
}
OFFICE_EXTENSIONS = {
    "word": {"doc", "docx"},
    "excel": {"xls", "xlsx"},
    "powerpoint": {"ppt", "pptx"},
}
WORKSPACE_LIMIT_MAX = 200


class LhiDocumentItem(models.Model):
    _inherit = "lhi.document.item"

    def _workspace_user(self):
        user_id = self.env.context.get("lhi_workspace_user_id")
        return self.env["res.users"].browse(user_id) if user_id else self.env.user

    @api.model
    def _business_links(self, record):
        project, award, grant_reference = super()._business_links(record)
        if not project and record and "order_id" in record._fields and record.order_id:
            order = record.order_id
            if "project_id" in order._fields and order.project_id:
                project = order.project_id
                award = project.award_id
        return project, award, grant_reference

    @api.model
    def _workspace_project(self, record):
        if record._name == "lhi.project":
            return record
        project, _award, _grant = self._business_links(record)
        return project

    @api.model
    def _workspace_domain(self, record, scope):
        direct = [
            ("linked_model", "=", record._name),
            ("linked_record_id", "=", record.id),
        ]
        project = self._workspace_project(record)
        if scope == "project" and project:
            return [("project_id", "=", project.id)]
        return direct

    @api.model
    def _workspace_filter_accessible(self, documents):
        user = self.env.user
        ids_by_model = defaultdict(set)
        for document in documents:
            ids_by_model[document.linked_model].add(document.linked_record_id)
        accessible = {}
        for model_name, record_ids in ids_by_model.items():
            if model_name not in self.env.registry:
                accessible[model_name] = set()
                continue
            model = self.env[model_name]
            try:
                accessible[model_name] = set(
                    model.search([("id", "in", list(record_ids))]).ids
                )
            except AccessError:
                accessible[model_name] = set()
        allowed_ids = []
        for document in documents:
            if document.linked_record_id not in accessible.get(
                document.linked_model, set()
            ):
                continue
            record = self.env[document.linked_model].browse(document.linked_record_id)
            if document.linked_field:
                field = record._fields.get(document.linked_field)
                if field and not record._has_field_access(field, "read"):
                    continue
            allowed_ids.append(document.id)
        return self.sudo().with_context(lhi_workspace_user_id=user.id).browse(
            allowed_ids
        )

    @api.model
    def _workspace_is_related(self, source_record, document):
        if (
            document.linked_model == source_record._name
            and document.linked_record_id == source_record.id
        ):
            return True
        project = self._workspace_project(source_record)
        return bool(project and document.project_id == project)

    @api.model
    def _workspace_document(self, source_record, document_uuid, operation="read"):
        user = self.env.user
        document = self.sudo().search(
            [
                ("uuid", "=", document_uuid),
                ("active", "=", True),
                ("storage_policy_id.workspace_enabled", "=", True),
            ],
            limit=1,
        )
        if not document or not self._workspace_is_related(source_record, document):
            raise AccessError(_("The document is outside this workspace."))
        document.with_user(user).check_linked_access(operation)
        return document.with_context(lhi_workspace_user_id=user.id)

    @api.model
    def _workspace_modified_by(self, document):
        try:
            payload = json.loads(document.modified_by or "{}")
        except (TypeError, ValueError):
            payload = {}
        identity = payload.get("user") or payload.get("application") or {}
        return identity.get("displayName") or identity.get("email") or ""

    @api.model
    def _workspace_office_type(self, document):
        extension = os.path.splitext(document.name or "")[1].lower().lstrip(".")
        for office_type, extensions in OFFICE_EXTENSIONS.items():
            if extension in extensions:
                return office_type
        return False

    def _workspace_is_locked(self):
        self.ensure_one()
        record = self._linked_record()
        if not record:
            return True
        for field_name in (
            "lhi_document_locked",
            "document_locked",
            "is_locked",
            "locked",
        ):
            if field_name in record._fields and bool(record[field_name]):
                return True
        lock_states = {
            value.strip().casefold()
            for value in (
                self.storage_policy_id.workspace_lock_states or ""
            ).split(",")
            if value.strip()
        }
        for field_name in ("state", "status"):
            if field_name in record._fields and record[field_name]:
                return str(record[field_name]).casefold() in lock_states
        return False

    @api.model
    def _workspace_can_write(self, document):
        if document._workspace_is_locked():
            return False
        try:
            document.with_user(document._workspace_user()).check_linked_access("write")
            return True
        except AccessError:
            return False

    @api.model
    def _workspace_serialize(self, document):
        office_type = self._workspace_office_type(document)
        can_write = self._workspace_can_write(document)
        return {
            "uuid": document.uuid,
            "name": document.name,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
            "category": document.document_category or "",
            "confidentiality": document.confidentiality,
            "workflow_state": document.workflow_state or "",
            "storage_state": document.storage_state,
            "version": document.sharepoint_version or "",
            "etag": document.sharepoint_etag or "",
            "modified_at": fields.Datetime.to_string(document.modified_at)
            if document.modified_at
            else False,
            "modified_by": self._workspace_modified_by(document),
            "office_type": office_type,
            "can_preview": document.storage_state == "available",
            "can_edit": bool(office_type and can_write),
            "can_write": can_write,
            "locked": document._workspace_is_locked(),
            "download_url": (
                f"/lhi/sharepoint/document/{document.uuid}/download"
                if document.storage_state == "available"
                else False
            ),
            "preview_url": (
                f"/lhi/document-workspace/preview/{document.uuid}"
                if document.storage_state == "available"
                else False
            ),
        }

    @api.model
    def _workspace_get(
        self,
        record,
        *,
        query="",
        category="",
        workflow_state="",
        scope="record",
        limit=100,
    ):
        limit = min(max(int(limit or 100), 1), WORKSPACE_LIMIT_MAX)
        domain = [
            ("active", "=", True),
            ("storage_policy_id.workspace_enabled", "=", True),
        ] + self._workspace_domain(record, scope)
        if query:
            domain.append(("name", "ilike", str(query)[:100]))
        if category:
            domain.append(("document_category", "=", str(category)[:100]))
        if workflow_state:
            domain.append(("workflow_state", "=", str(workflow_state)[:100]))
        candidates = self.sudo().search(
            domain, order="modified_at desc nulls last, id desc", limit=limit + 1
        )
        truncated = len(candidates) > limit
        documents = self._workspace_filter_accessible(candidates[:limit])
        project = self._workspace_project(record)
        serialized = [self._workspace_serialize(value) for value in documents]
        return {
            "documents": serialized,
            "categories": sorted(
                {value["category"] for value in serialized if value["category"]}
            ),
            "workflow_states": sorted(
                {
                    value["workflow_state"]
                    for value in serialized
                    if value["workflow_state"]
                }
            ),
            "scope": scope if scope in ("record", "project") else "record",
            "project_scope_available": bool(project),
            "project_name": project.display_name if project else False,
            "truncated": truncated,
            "limit": limit,
        }

    def _workspace_assert_write(self):
        self.ensure_one()
        self.with_user(self._workspace_user()).check_linked_access("write")
        if self._workspace_is_locked():
            raise AccessError(_("This document is locked by its business workflow."))

    def _workspace_current_payload(self):
        self.ensure_one()
        user = self._workspace_user()
        payload = self.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}"
            ),
            auth_context="delegated",
            user=user,
            params={
                "$select": (
                    "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,"
                    "lastModifiedBy,parentReference,file"
                )
            },
        )
        if payload.get("id") != self.sharepoint_item_id:
            raise AccessError(_("SharePoint returned a different document item."))
        self.sudo()._apply_drive_item(payload)
        return payload

    def _workspace_preview_payload(self, user=None):
        self.ensure_one()
        user = user or self._workspace_user()
        self.with_user(user).check_linked_access("read")
        if not self.storage_policy_id.workspace_enabled:
            raise AccessError(_("This document is not enabled for workspace access."))
        if self.storage_state != "available":
            raise UserError(_("The document is not available for preview."))
        payload = self.graph_connection_id.graph_request(
            "POST",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}/preview"
            ),
            auth_context="delegated",
            user=user,
            json_body={},
            expected_statuses={200},
        )
        for key in ("getUrl", "postUrl"):
            value = payload.get(key)
            if value:
                parsed = urlparse(value)
                if parsed.scheme != "https" or not parsed.netloc:
                    raise UserError(_("Microsoft returned an unsafe preview URL."))
        if not payload.get("getUrl") and not payload.get("postUrl"):
            raise UserError(_("Microsoft did not return a preview action URL."))
        return payload

    @api.model
    def _workspace_browser_url(self, url):
        parsed = urlparse(url or "")
        if parsed.scheme != "https" or not parsed.netloc:
            raise UserError(_("SharePoint did not return a secure document URL."))
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["web"] = "1"
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _workspace_audit(self, event_type, description, old_value=None, new_value=None):
        self.ensure_one()
        self.env["lhi.audit.log"].with_user(self._workspace_user()).create_event(
            event_type=event_type,
            res_model=self.linked_model,
            res_id=self.linked_record_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
        )

    @api.model
    def _workspace_action(self, record, document_uuid, action):
        user = self.env.user
        document = self._workspace_document(record, document_uuid, "read")
        if document.storage_state != "available":
            raise UserError(_("The document is not currently available in SharePoint."))
        if action in ("edit", "desktop", "new_version", "replace", "archive"):
            document._workspace_assert_write()
        if action == "download":
            document._workspace_audit(
                "document_download",
                _("Downloaded '%s' from SharePoint.") % document.name,
            )
            return {
                "url": f"/lhi/sharepoint/document/{document.uuid}/download"
            }
        if action in ("edit", "desktop", "governed_link"):
            payload = document._workspace_current_payload()
            web_url = self._workspace_browser_url(payload.get("webUrl"))
            if action == "edit":
                document._workspace_audit(
                    "document_edit",
                    _("Opened '%s' in Microsoft 365.") % document.name,
                )
                return {"url": web_url, "etag": document.sharepoint_etag}
            if action == "desktop":
                office_type = self._workspace_office_type(document)
                if not office_type:
                    raise ValidationError(
                        _("Only Word, Excel, and PowerPoint documents have desktop actions.")
                    )
                document._workspace_audit(
                    "document_edit",
                    _("Opened '%s' in the Microsoft desktop application.") % document.name,
                )
                return {"url": f"{OFFICE_SCHEMES[office_type]}:ofe|u|{web_url}"}
            document._workspace_audit(
                "document_link_copy",
                _("Copied the governed SharePoint link for '%s'.") % document.name,
            )
            return {"url": web_url}
        if action in ("new_version", "replace"):
            session = document.graph_connection_id.graph_request(
                "POST",
                (
                    f"/drives/{quote(document.sharepoint_drive_id)}/items/"
                    f"{quote(document.sharepoint_item_id)}/createUploadSession"
                ),
                auth_context="delegated",
                user=user,
                headers={"If-Match": document.sharepoint_etag}
                if document.sharepoint_etag
                else None,
                json_body={
                    "item": {
                        "@microsoft.graph.conflictBehavior": "replace",
                        "name": document.name,
                    }
                },
                expected_statuses={200, 201},
            )
            document.graph_connection_id._lhi_validate_upload_url(
                session.get("uploadUrl")
            )
            document.sudo().write(
                {
                    "upload_url": session["uploadUrl"],
                    "upload_session_expiration": document._parse_graph_datetime(
                        session.get("expirationDateTime")
                    ),
                    "upload_state": "session",
                }
            )
            return {
                "document_uuid": document.uuid,
                "upload_url": session["uploadUrl"],
                "chunk_size": document.storage_policy_id.upload_chunk_size_kb * 1024,
                "expected_name": document.name,
                "maximum_size": document.storage_policy_id.maximum_size_mb
                * 1024
                * 1024,
            }
        if action == "archive":
            old_state = document.storage_state
            headers = (
                {"If-Match": document.sharepoint_etag}
                if document.sharepoint_etag
                else None
            )
            document.graph_connection_id.graph_request(
                "DELETE",
                (
                    f"/drives/{quote(document.sharepoint_drive_id)}/items/"
                    f"{quote(document.sharepoint_item_id)}"
                ),
                auth_context="delegated",
                user=user,
                headers=headers,
                expected_statuses={204},
            )
            document.sudo().write(
                {
                    "storage_state": "archived",
                    "upload_state": "completed",
                    "active": False,
                    "last_sync_at": fields.Datetime.now(),
                }
            )
            document.message_post(
                body=_("Document moved to the SharePoint recycle bin.")
            )
            document._workspace_audit(
                "document_archive",
                _("Archived '%s' in SharePoint.") % document.name,
                old_state,
                "archived",
            )
            return {"archived": True}
        raise ValidationError(_("The requested document action is not supported."))

    @api.model
    def _workspace_refresh(self, record, document_uuids):
        result = []
        for document_uuid in list(dict.fromkeys(document_uuids or []))[:50]:
            document = self._workspace_document(record, document_uuid, "read")
            if document.storage_state != "available":
                continue
            old_etag = document.sharepoint_etag
            document._workspace_current_payload()
            value = self._workspace_serialize(document)
            value["newer"] = bool(old_etag and old_etag != document.sharepoint_etag)
            result.append(value)
        return result

    @api.model
    def _workspace_versions(self, record, document_uuid):
        user = self.env.user
        document = self._workspace_document(record, document_uuid, "read")
        versions = document.graph_connection_id.graph_get_all(
            (
                f"/drives/{quote(document.sharepoint_drive_id)}/items/"
                f"{quote(document.sharepoint_item_id)}/versions"
            ),
            auth_context="delegated",
            user=user,
            params={
                "$select": "id,size,lastModifiedDateTime,lastModifiedBy,publication"
            },
            max_pages=10,
            max_items=100,
        )
        return [
            {
                "id": value.get("id"),
                "size": int(value.get("size") or 0),
                "modified_at": value.get("lastModifiedDateTime"),
                "modified_by": (
                    (value.get("lastModifiedBy") or {}).get("user") or {}
                ).get("displayName", ""),
            }
            for value in versions
        ]

    @api.model
    def _workspace_templates(self, record):
        record.check_access("write")
        templates = self.env["lhi.document.template"].sudo().search(
            [
                ("active", "=", True),
                ("state", "=", "approved"),
                ("company_id", "=", self.env.company.id),
                ("model_name", "=", record._name),
            ],
            order="sequence, name",
            limit=50,
        )
        return [
            {
                "id": template.id,
                "name": template.name,
                "file_type": template.file_type,
                "source_name": template.source_name,
            }
            for template in templates
        ]

    @api.model
    def _workspace_create_from_template(
        self, record, template_id, filename, idempotency_key
    ):
        record.check_access("write")
        template = self.env["lhi.document.template"].sudo().search(
            [
                ("id", "=", int(template_id)),
                ("active", "=", True),
                ("state", "=", "approved"),
                ("company_id", "=", self.env.company.id),
                ("model_name", "=", record._name),
            ],
            limit=1,
        )
        if not template:
            raise AccessError(_("The selected template is unavailable for this workspace."))
        filename = template.graph_connection_id._lhi_safe_segment(filename)
        extension = os.path.splitext(filename)[1].lower().lstrip(".")
        if extension not in OFFICE_EXTENSIONS[template.file_type]:
            source_extension = os.path.splitext(template.source_name)[1]
            filename = f"{filename.rstrip('.')}{source_extension}"
        stable_key = hashlib.sha256(
            (
                f"workspace-template|{self.env.cr.dbname}|{self.env.user.id}|"
                f"{record._name}|{record.id}|{template.id}|{idempotency_key}"
            ).encode()
        ).hexdigest()
        existing = self.sudo().search([("idempotency_key", "=", stable_key)], limit=1)
        if existing:
            existing = existing.with_context(
                lhi_workspace_user_id=self.env.user.id
            )
            result = self._workspace_serialize(existing)
            if existing.storage_state == "available":
                result["edit_url"] = self._workspace_browser_url(
                    existing.sharepoint_web_url
                )
            return result
        policy = self.env["lhi.document.storage.policy"].resolve_policy(
            record._name, False, self.env.company
        )
        if not policy or policy.storage_backend != "sharepoint":
            raise ValidationError(
                _("No SharePoint storage policy is configured for this workspace.")
            )
        source_payload = template.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(template.source_drive_id)}/items/"
                f"{quote(template.source_item_id)}"
            ),
            auth_context="delegated",
            user=self.env.user,
            params={"$select": "id,name,size,file,@microsoft.graph.downloadUrl"},
        )
        if source_payload.get("id") != template.source_item_id:
            raise AccessError(_("SharePoint template validation failed."))
        source_size = int(source_payload.get("size") or 0)
        if source_size <= 0 or source_size > policy.small_upload_limit_mb * 1024 * 1024:
            raise ValidationError(
                _(
                    "Templates must be non-empty and no larger than the policy's "
                    "small-upload limit."
                )
            )
        response = template.graph_connection_id.lhi_upload_session_request(
            "GET",
            source_payload.get("@microsoft.graph.downloadUrl"),
            expected_statuses={200},
            auth_context="delegated",
            user=self.env.user,
        )
        content = response.content
        if len(content) != source_size:
            raise UserError(_("The SharePoint template download was incomplete."))
        policy.validate_file(filename, len(content))
        project, award, grant_reference = self._business_links(record)
        document = self.sudo().create(
            {
                "name": filename,
                "mime_type": (source_payload.get("file") or {}).get("mimeType")
                or template.source_mime_type
                or "application/octet-stream",
                "file_size": len(content),
                "checksum": hashlib.sha256(content).hexdigest(),
                "sha1_checksum": hashlib.sha1(content).hexdigest(),
                "company_id": self.env.company.id,
                "requested_by_id": self.env.user.id,
                "graph_connection_id": template.graph_connection_id.id,
                "storage_policy_id": policy.id,
                "linked_model": record._name,
                "linked_record_id": record.id,
                "linked_record_uuid": (
                    record.uuid
                    if "uuid" in record._fields and record.uuid
                    else f"{record._name}:{record.id}"
                ),
                "project_id": project.id if project else False,
                "award_id": award.id if award else False,
                "grant_reference": grant_reference,
                "document_category": policy.document_category,
                "confidentiality": policy.confidentiality,
                "workflow_state": (
                    str(record.state)
                    if "state" in record._fields and record.state
                    else False
                ),
                "retention_category": policy.retention_category,
                "idempotency_key": stable_key,
                "storage_state": "uploading",
                "upload_state": "uploading",
            }
        )
        document = document.with_context(lhi_workspace_user_id=self.env.user.id)
        try:
            library = template.graph_connection_id.lhi_get_library(policy.library_code)
            document._ensure_project_template(library, "delegated", self.env.user)
            parent_id = template.graph_connection_id.lhi_ensure_folder_path(
                library,
                document._folder_path(),
                auth_context="delegated",
                user=self.env.user,
            )
            payload = template.graph_connection_id.lhi_upload_small(
                library,
                parent_id,
                filename,
                content,
                conflict_behavior="fail",
                auth_context="delegated",
                user=self.env.user,
                mimetype=document.mime_type,
            )
            document.sudo().write(
                {
                    "sharepoint_drive_id": library.drive_id,
                    "sharepoint_parent_item_id": parent_id,
                }
            )
            document._apply_drive_item(payload)
            document._patch_sharepoint_metadata(
                auth_context="delegated", user=self.env.user
            )
            document._verify_drive_item(
                auth_context="delegated", user=self.env.user
            )
            document.sudo().write(
                {
                    "storage_state": "available",
                    "upload_state": "completed",
                    "reconciliation_state": "matched",
                    "last_error": False,
                }
            )
        except Exception as error:
            document._mark_failed(error, enqueue=False)
            raise
        document._workspace_audit(
            "document_create",
            _("Created '%s' from approved template '%s'.")
            % (document.name, template.name),
        )
        result = self._workspace_serialize(document)
        result["edit_url"] = self._workspace_browser_url(
            document.sharepoint_web_url
        )
        return result

    def _workspace_confirm_version(self, remote_item_id):
        self.ensure_one()
        self._workspace_assert_write()
        if self.upload_state != "session":
            raise ValidationError(_("The SharePoint upload session is no longer active."))
        if (
            self.upload_session_expiration
            and self.upload_session_expiration < fields.Datetime.now()
        ):
            raise ValidationError(_("The SharePoint upload session has expired."))
        if remote_item_id != self.sharepoint_item_id:
            raise ValidationError(_("SharePoint returned a different immutable item ID."))
        old_version = self.sharepoint_version
        old_etag = self.sharepoint_etag
        payload = self._workspace_current_payload()
        if old_etag and payload.get("eTag") == old_etag:
            raise ValidationError(_("SharePoint did not confirm a new document version."))
        if int(payload.get("size") or 0) <= 0:
            raise ValidationError(_("SharePoint returned an empty replacement document."))
        self.storage_policy_id.validate_file(
            payload.get("name") or self.name, int(payload["size"])
        )
        self.sudo().write(
            {
                "file_size": int(payload["size"]),
                "upload_state": "verifying",
                "storage_state": "uploading",
            }
        )
        self._calculate_remote_hashes(auth_context="delegated", user=self.env.user)
        self._patch_sharepoint_metadata(
            auth_context="delegated", user=self.env.user
        )
        self._verify_drive_item(auth_context="delegated", user=self.env.user)
        self.sudo().write(
            {
                "storage_state": "available",
                "upload_state": "completed",
                "reconciliation_state": "matched",
                "upload_url": False,
                "upload_session_expiration": False,
                "last_error": False,
            }
        )
        self._workspace_audit(
            "document_version",
            _("Uploaded a new SharePoint version for '%s'.") % self.name,
            old_version,
            self.sharepoint_version,
        )
        return self._workspace_serialize(self)
