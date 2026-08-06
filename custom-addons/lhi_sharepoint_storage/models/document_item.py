import base64
import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)
PROJECT_SUBFOLDERS = (
    "01 Proposal",
    "02 Award and Agreement",
    "03 Workplans",
    "04 MEAL and Evidence",
    "05 Procurement",
    "06 Reports",
    "07 Partners",
    "08 Compliance and Audit",
    "09 Closeout",
)


class LhiDocumentItem(models.Model):
    _name = "lhi.document.item"
    _description = "LHI SharePoint Document Item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    MEMO_STORAGE_CONTRACT_VERSION = 1

    uuid = fields.Char(
        required=True, default=lambda self: str(uuid.uuid4()), copy=False, index=True
    )
    active = fields.Boolean(default=True)
    name = fields.Char(required=True, tracking=True)
    mime_type = fields.Char(required=True)
    file_size = fields.Integer(required=True)
    checksum = fields.Char(string="SHA-256 Checksum", index=True)
    sha1_checksum = fields.Char(index=True)
    quickxor_hash = fields.Char(readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    requested_by_id = fields.Many2one("res.users", required=True, index=True)
    graph_connection_id = fields.Many2one(
        "lhi.graph.connection", required=True, ondelete="restrict", index=True
    )
    storage_policy_id = fields.Many2one(
        "lhi.document.storage.policy", required=True, ondelete="restrict", index=True
    )
    attachment_ids = fields.One2many(
        "ir.attachment", "lhi_document_item_id", string="Odoo Attachment Links"
    )

    sharepoint_site_id = fields.Char(readonly=True, index=True)
    sharepoint_drive_id = fields.Char(readonly=True, index=True)
    sharepoint_item_id = fields.Char(readonly=True, index=True)
    sharepoint_parent_item_id = fields.Char(readonly=True)
    sharepoint_web_url = fields.Char(readonly=True)
    sharepoint_etag = fields.Char(readonly=True)
    sharepoint_version = fields.Char(readonly=True)
    modified_at = fields.Datetime(readonly=True)
    modified_by = fields.Char(readonly=True)

    storage_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("uploading", "Uploading"),
            ("available", "Available"),
            ("failed", "Failed"),
            ("archived", "Archived"),
            ("deleted", "Deleted"),
            ("missing", "Missing"),
            ("mismatch", "Metadata Mismatch"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    upload_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("session", "Upload Session Created"),
            ("uploading", "Uploading"),
            ("verifying", "Verifying"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    linked_model = fields.Char(required=True, index=True)
    linked_record_id = fields.Integer(required=True, index=True)
    linked_record_uuid = fields.Char(index=True)
    linked_field = fields.Char(index=True)
    project_id = fields.Many2one("lhi.project", index=True)
    award_id = fields.Many2one("lhi.award", index=True)
    grant_reference = fields.Char(index=True)
    document_category = fields.Char(index=True)
    confidentiality = fields.Selection(
        [
            ("internal", "Internal"),
            ("confidential", "Confidential"),
            ("restricted", "Restricted"),
        ],
        default="internal",
        required=True,
        index=True,
    )
    workflow_state = fields.Char(index=True)
    retention_category = fields.Char(index=True)
    last_sync_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    upload_attempts = fields.Integer(default=0, readonly=True)
    reconciliation_state = fields.Selection(
        [
            ("not_checked", "Not Checked"),
            ("matched", "Matched"),
            ("missing", "Missing"),
            ("mismatch", "Mismatch"),
            ("failed", "Check Failed"),
        ],
        default="not_checked",
        required=True,
        readonly=True,
        index=True,
    )
    idempotency_key = fields.Char(required=True, copy=False, index=True)
    upload_session_expiration = fields.Datetime(readonly=True, copy=False)
    upload_next_offset = fields.Integer(default=0, readonly=True, copy=False)
    upload_url = fields.Char(groups="base.group_no_one", copy=False)
    spool_path = fields.Char(groups="base.group_no_one", copy=False)

    _uuid_unique = models.Constraint("unique(uuid)", "Document UUIDs must be unique.")
    _idempotency_unique = models.Constraint(
        "unique(idempotency_key)", "Document idempotency keys must be unique."
    )
    _drive_item_unique = models.Constraint(
        "unique(sharepoint_drive_id, sharepoint_item_id)",
        "A SharePoint DriveItem can only be registered once.",
    )

    @api.constrains(
        "file_size",
        "linked_record_id",
        "storage_state",
        "sharepoint_site_id",
        "sharepoint_drive_id",
        "sharepoint_item_id",
    )
    def _check_document_invariants(self):
        for item in self:
            if item.file_size <= 0 or item.linked_record_id <= 0:
                raise ValidationError(_("Document size and linked record ID must be positive."))
            if item.storage_state == "available" and not (
                item.sharepoint_site_id
                and item.sharepoint_drive_id
                and item.sharepoint_item_id
            ):
                raise ValidationError(
                    _(
                        "A document cannot be marked available before SharePoint "
                        "confirms the site, drive, and immutable item identifiers."
                    )
                )

    def _linked_record(self):
        self.ensure_one()
        if self.linked_model not in self.env.registry:
            return self.env["ir.model"].browse()
        return self.env[self.linked_model].browse(self.linked_record_id).exists()

    def check_linked_access(self, operation="read"):
        for item in self:
            record = item._linked_record()
            if not record:
                raise AccessError(_("The linked business record no longer exists."))
            record.check_access(operation)
            if item.linked_field:
                field = record._fields.get(item.linked_field)
                if field and not record._has_field_access(field, operation):
                    raise AccessError(_("You cannot access this document field."))
        return True

    @api.model
    def _connection_for_company(self, company):
        return self.env["lhi.graph.connection"].sudo()._get_active_connection(company)

    @api.model
    def _spool_directory(self):
        path = os.environ.get(
            "LHI_SHAREPOINT_SPOOL_DIR", "/var/lib/odoo/lhi-sharepoint-spool"
        )
        os.makedirs(path, mode=0o700, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def _write_spool(self, content):
        self.ensure_one()
        directory = self._spool_directory()
        descriptor, path = tempfile.mkstemp(
            prefix=f"{self.uuid}-", suffix=".pending", dir=directory
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        self.sudo().write({"spool_path": path})

    def _remove_spool(self):
        for item in self:
            path = item.sudo().spool_path
            if path:
                item.sudo().write({"spool_path": False})

                @item.env.cr.postcommit.add
                def _delete_committed_spool(path=path, document_uuid=item.uuid):
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        _logger.exception(
                            "Could not remove committed SharePoint spool file for document %s",
                            document_uuid,
                        )

    @api.model
    def _decode_binary_value(self, value):
        if not value:
            return b""
        if isinstance(value, str):
            value = value.encode()
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            return value

    @api.model
    def _business_links(self, record):
        project = self.env["lhi.project"]
        award = self.env["lhi.award"]
        candidates = [record]
        for path in (
            "meal_data_id",
            "workplan_id",
            "request_id",
            "sourcing_id",
            "report_id",
        ):
            if record and path in record._fields and record[path]:
                candidates.append(record[path])
        for candidate in candidates:
            for field_name in ("project_id", "lhi_project_id"):
                if (
                    candidate
                    and field_name in candidate._fields
                    and candidate[field_name]
                    and candidate[field_name]._name == "lhi.project"
                ):
                    project = candidate[field_name]
                    break
            if project:
                break
        if project and project.award_id:
            award = project.award_id
        elif record and "award_id" in record._fields and record.award_id:
            award = record.award_id
        grant_reference = False
        for candidate in candidates:
            for field_name in ("grant_id", "lhi_grant_id", "grant_reference"):
                if candidate and field_name in candidate._fields and candidate[field_name]:
                    value = candidate[field_name]
                    grant_reference = value.display_name if hasattr(value, "display_name") else str(value)
                    break
            if grant_reference:
                break
        return project, award, grant_reference

    @api.model
    def _make_idempotency_key(
        self, linked_model, linked_record_id, linked_field, name, checksum
    ):
        raw = "|".join(
            [
                self.env.cr.dbname,
                linked_model,
                str(linked_record_id),
                linked_field or "",
                name,
                checksum,
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    @api.model
    def create_from_bytes(
        self,
        *,
        name,
        content,
        mime_type,
        linked_model,
        linked_record_id,
        linked_field=False,
        policy=None,
        requested_by=None,
        attachment=None,
        synchronous=True,
    ):
        requested_by = requested_by or self.env.user
        record = self.env[linked_model].browse(linked_record_id).exists()
        if not record:
            raise ValidationError(_("The linked business record does not exist."))
        record.with_user(requested_by).check_access("write")
        company = (
            record.company_id
            if "company_id" in record._fields and record.company_id
            else requested_by.company_id
        )
        policy = policy or self.env["lhi.document.storage.policy"].resolve_policy(
            linked_model, linked_field, company
        )
        if not policy or policy.storage_backend != "sharepoint":
            raise ValidationError(_("No SharePoint storage policy applies to this document."))
        policy.validate_file(name, len(content))
        checksum = hashlib.sha256(content).hexdigest()
        sha1_checksum = hashlib.sha1(content).hexdigest()
        key = self._make_idempotency_key(
            linked_model, linked_record_id, linked_field, name, checksum
        )
        existing = self.sudo().search([("idempotency_key", "=", key)], limit=1)
        if existing:
            if attachment:
                attachment.with_context(lhi_sharepoint_skip_adapter=True).sudo().write(
                    {"lhi_document_item_id": existing.id, "raw": False}
                )
            return existing
        project, award, grant_reference = self._business_links(record)
        connection = self._connection_for_company(company)
        item = self.sudo().create(
            {
                "name": name,
                "mime_type": mime_type or "application/octet-stream",
                "file_size": len(content),
                "checksum": checksum,
                "sha1_checksum": sha1_checksum,
                "company_id": company.id,
                "requested_by_id": requested_by.id,
                "graph_connection_id": connection.id,
                "storage_policy_id": policy.id,
                "linked_model": linked_model,
                "linked_record_id": linked_record_id,
                "linked_field": linked_field or False,
                "linked_record_uuid": (
                    record.uuid
                    if "uuid" in record._fields and record.uuid
                    else f"{linked_model}:{linked_record_id}"
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
                "idempotency_key": key,
            }
        )
        item._write_spool(content)
        if attachment:
            attachment.with_context(lhi_sharepoint_skip_adapter=True).sudo().write(
                {"lhi_document_item_id": item.id, "raw": False}
            )
        if synchronous:
            try:
                item.action_upload()
            except Exception as error:
                item._mark_failed(error, enqueue=False)
                raise
        else:
            item._enqueue("upload")
        return item

    def _folder_path(self):
        self.ensure_one()
        policy = self.storage_policy_id
        if policy.folder_strategy == "library_root":
            return ""
        if policy.folder_strategy == "fixed_path":
            return policy.fixed_folder_path or ""
        if policy.folder_strategy == "project_workspace" and self.project_id:
            parts = [self.project_id.code or self.project_id.name]
            if policy.project_subfolder:
                parts.append(policy.project_subfolder)
            return "/".join(parts)
        record_label = self.linked_model.replace(".", " ").title()
        return f"{record_label}/{self.linked_record_uuid or self.linked_record_id}"

    def _ensure_project_template(self, library, auth_context, user):
        self.ensure_one()
        if (
            self.storage_policy_id.folder_strategy != "project_workspace"
            or not self.project_id
        ):
            return
        root = self.graph_connection_id.lhi_ensure_folder_path(
            library,
            self.project_id.code or self.project_id.name,
            auth_context=auth_context,
            user=user,
        )
        for folder in PROJECT_SUBFOLDERS:
            self.graph_connection_id.lhi_ensure_folder_path(
                library,
                f"{self.project_id.code or self.project_id.name}/{folder}",
                auth_context=auth_context,
                user=user,
            )
        return root

    def _read_spool(self):
        self.ensure_one()
        path = self.sudo().spool_path
        if not path or not os.path.isfile(path):
            raise UserError(_("The temporary upload payload is missing."))
        real_directory = os.path.realpath(self._spool_directory())
        real_path = os.path.realpath(path)
        if os.path.commonpath([real_directory, real_path]) != real_directory:
            raise ValidationError(_("The temporary upload path is unsafe."))
        with open(real_path, "rb") as stream:
            return stream.read()

    def _apply_drive_item(self, payload):
        self.ensure_one()
        parent = payload.get("parentReference") or {}
        hashes = (payload.get("file") or {}).get("hashes") or {}
        modified = self._parse_graph_datetime(payload.get("lastModifiedDateTime"))
        vals = {
            "sharepoint_site_id": self.graph_connection_id.sharepoint_site_id,
            "sharepoint_drive_id": parent.get("driveId")
            or self.sharepoint_drive_id,
            "sharepoint_item_id": payload.get("id"),
            "sharepoint_parent_item_id": parent.get("id")
            or self.sharepoint_parent_item_id,
            "sharepoint_web_url": payload.get("webUrl"),
            "sharepoint_etag": payload.get("eTag"),
            "sharepoint_version": payload.get("cTag") or payload.get("eTag"),
            "quickxor_hash": hashes.get("quickXorHash"),
            "modified_at": modified,
            "modified_by": json.dumps(payload.get("lastModifiedBy") or {})[:1000],
            "last_sync_at": fields.Datetime.now(),
        }
        if not vals["sharepoint_item_id"] or not vals["sharepoint_drive_id"]:
            raise UserError(_("SharePoint did not return an immutable DriveItem identifier."))
        self.sudo().write(vals)

    @api.model
    def _parse_graph_datetime(self, value):
        if not value:
            return False
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _sharepoint_document_class(self):
        self.ensure_one()
        policy = self.storage_policy_id
        category = (self.document_category or "").lower()
        if policy.library_code == "signed_documents":
            return "Signed Document"
        if policy.library_code == "controlled_documents":
            return "Controlled Document"
        if policy.library_code == "procurement":
            return "Procurement"
        if policy.library_code == "operations":
            return "Operations"
        if "proposal" in category:
            return "Proposal"
        if "award" in category or "agreement" in category:
            return "Award"
        if "meal" in category or "evidence" in category:
            return "MEAL Evidence"
        if "partner" in category or "vendor" in category:
            return "Partner"
        if "compliance" in category or "audit" in category:
            return "Compliance"
        return "Project"

    def _default_retention_category(self):
        self.ensure_one()
        return {
            "projects": "Grant Record",
            "procurement": "Procurement Record",
            "operations": "Operational",
            "controlled_documents": "Controlled Record",
            "signed_documents": "Signed Record",
        }[self.storage_policy_id.library_code]

    def _patch_sharepoint_metadata(self, auth_context="application", user=None):
        self.ensure_one()
        metadata = {
            "LhiOdooDatabase": self.env.cr.dbname,
            "LhiOdooModel": self.linked_model,
            "LhiOdooRecordId": self.linked_record_id,
            "LhiCompanyCode": self.company_id.name,
            "LhiDocumentClass": self._sharepoint_document_class(),
            "LhiWorkflowState": self.workflow_state or "",
            "LhiContentSha256": self.checksum or "",
            "LhiAuditCorrelationId": self.uuid,
            "LhiRetentionCategory": (
                self.retention_category or self._default_retention_category()
            ),
        }
        metadata.update(json.loads(self.storage_policy_id.required_metadata_json or "{}"))
        self.graph_connection_id.graph_request(
            "PATCH",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}/listItem/fields"
            ),
            auth_context=auth_context,
            user=user,
            json_body=metadata,
            expected_statuses={200},
        )

    def _verify_drive_item(self, auth_context="application", user=None):
        self.ensure_one()
        payload = self.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}"
            ),
            auth_context=auth_context,
            user=user,
            params={
                "$select": (
                    "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,"
                    "lastModifiedBy,parentReference,file"
                )
            },
        )
        if payload.get("id") != self.sharepoint_item_id:
            raise UserError(_("SharePoint DriveItem verification failed."))
        if int(payload.get("size") or -1) != self.file_size:
            raise UserError(_("SharePoint file-size verification failed."))
        remote_sha1 = ((payload.get("file") or {}).get("hashes") or {}).get("sha1Hash")
        if remote_sha1 and remote_sha1.lower() != (self.sha1_checksum or "").lower():
            raise UserError(_("SharePoint checksum verification failed."))
        self._apply_drive_item(payload)
        return payload

    def _calculate_remote_hashes(self, auth_context="application", user=None):
        self.ensure_one()
        user = user or self.env.user
        response = self.graph_connection_id.lhi_binary_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}/content"
            ),
            auth_context=auth_context,
            user=user,
            expected_statuses={200},
            allow_redirects=True,
        )
        if not response or not response.content:
            raise UserError(_("SharePoint remote file content is empty."))
        content = response.content
        sha256 = hashlib.sha256(content).hexdigest()
        sha1 = hashlib.sha1(content).hexdigest()
        size = len(content)
        self.sudo().write(
            {"checksum": sha256, "sha1_checksum": sha1, "file_size": size}
        )
        return True

    def _refresh_drive_item_after_metadata(self, auth_context="application", user=None):
        self.ensure_one()
        payload = self.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}"
            ),
            auth_context=auth_context,
            user=user,
            params={
                "$select": (
                    "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,"
                    "lastModifiedBy,parentReference,file"
                )
            },
        )
        if not payload or payload.get("id") != self.sharepoint_item_id:
            raise UserError(_("SharePoint DriveItem post-metadata verification failed."))
        self._apply_drive_item(payload)
        if payload.get("name"):
            self.sudo().write({"name": payload.get("name")})
        final_size = int(payload.get("size") or 0)
        if final_size <= 0:
            raise UserError(_("Invalid remote file size after metadata promotion."))
        self.sudo().write({"file_size": final_size})
        self._calculate_remote_hashes(auth_context=auth_context, user=user)
        return payload

    def _upload_large(self, library, parent_id, content):
        self.ensure_one()
        connection = self.graph_connection_id
        session_valid = (
            self.sudo().upload_url
            and self.upload_session_expiration
            and self.upload_session_expiration
            > fields.Datetime.now() + timedelta(minutes=2)
        )
        if not session_valid:
            session = connection.lhi_create_upload_session(
                library,
                parent_id,
                self.name,
                conflict_behavior=self.storage_policy_id.conflict_behavior,
            )
            self.sudo().write(
                {
                    "upload_url": session["uploadUrl"],
                    "upload_session_expiration": self._parse_graph_datetime(
                        session.get("expirationDateTime")
                    ),
                    "upload_next_offset": 0,
                    "upload_state": "session",
                }
            )
        offset = self.upload_next_offset
        chunk_size = self.storage_policy_id.upload_chunk_size_kb * 1024
        final_payload = None
        while offset < len(content):
            end = min(offset + chunk_size, len(content))
            chunk = content[offset:end]
            response = connection.lhi_upload_session_request(
                "PUT",
                self.sudo().upload_url,
                data=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end - 1}/{len(content)}",
                },
            )
            payload = response.json()
            if response.status_code == 202:
                ranges = payload.get("nextExpectedRanges") or [f"{end}-"]
                try:
                    offset = int(str(ranges[0]).split("-", 1)[0])
                except (TypeError, ValueError):
                    offset = end
                self.sudo().write({"upload_next_offset": offset})
            else:
                final_payload = payload
                offset = len(content)
        if not final_payload:
            raise UserError(_("SharePoint did not complete the upload session."))
        return final_payload

    def action_upload(self):
        for item in self:
            if item.storage_state == "available":
                continue
            content = item._read_spool()
            if hashlib.sha256(content).hexdigest() != item.checksum:
                raise UserError(_("The temporary upload checksum does not match."))
            policy = item.storage_policy_id
            policy.validate_file(item.name, len(content))
            item.sudo().write(
                {
                    "storage_state": "uploading",
                    "upload_state": "uploading",
                    "upload_attempts": item.upload_attempts + 1,
                    "last_error": False,
                }
            )
            library = item.graph_connection_id.lhi_get_library(policy.library_code)
            item._ensure_project_template(library, "application", None)
            parent_id = item.graph_connection_id.lhi_ensure_folder_path(
                library, item._folder_path()
            )
            item.sudo().write(
                {
                    "sharepoint_drive_id": library.drive_id,
                    "sharepoint_parent_item_id": parent_id,
                }
            )
            use_small_upload = (
                len(content) <= policy.small_upload_limit_mb * 1024 * 1024
                and policy.conflict_behavior == "replace"
            )
            if use_small_upload:
                payload = item.graph_connection_id.lhi_upload_small(
                    library,
                    parent_id,
                    item.name,
                    content,
                    conflict_behavior=policy.conflict_behavior,
                    mimetype=item.mime_type,
                )
            else:
                payload = item._upload_large(library, parent_id, content)
            item._apply_drive_item(payload)
            if payload.get("name"):
                item.sudo().write({"name": payload.get("name")})
            item.sudo().write({"upload_state": "verifying"})
            item._verify_drive_item()
            item._patch_sharepoint_metadata()
            item._refresh_drive_item_after_metadata()
            item.sudo().write(
                {
                    "storage_state": "available",
                    "upload_state": "completed",
                    "reconciliation_state": "matched",
                    "last_error": False,
                    "upload_url": False,
                    "upload_session_expiration": False,
                }
            )
            item._remove_spool()
            item.message_post(body=_("Document storage confirmed by SharePoint."))
        return True

    def _mark_failed(self, error, enqueue=False):
        safe_error = self.graph_connection_id._redact_text(str(error))[:2000]
        self.sudo().write(
            {
                "storage_state": "failed",
                "upload_state": "failed",
                "last_error": safe_error,
            }
        )
        self.message_post(body=_("SharePoint document operation failed: %s") % safe_error)
        if enqueue:
            self._enqueue("upload")

    def _enqueue(self, action):
        self.ensure_one()
        return self.env["lhi.integration.job"].sudo().lhi_create_idempotent_job(
            model_name=self._name,
            record_id=self.id,
            action=action,
            idempotency_key=f"sharepoint:{self.uuid}:{action}",
            description=_("SharePoint document %s operation") % action,
            company=self.company_id,
        )

    def action_retry(self):
        for item in self:
            item.check_linked_access("write")
            item.sudo().write(
                {"storage_state": "pending", "upload_state": "pending", "last_error": False}
            )
            self.env["lhi.integration.job"].sudo().search(
                [
                    ("lhi_idempotency_key", "=", f"sharepoint:{item.uuid}:upload"),
                    ("state", "=", "dead_letter"),
                ]
            ).write(
                {
                    "state": "pending",
                    "retry_count": 0,
                    "next_retry": False,
                    "last_error": False,
                }
            )
            item._enqueue("upload")
        return True

    def action_reconcile(self):
        for item in self:
            if not item.sharepoint_item_id:
                item.sudo().write(
                    {
                        "reconciliation_state": "missing",
                        "storage_state": "missing",
                        "last_sync_at": fields.Datetime.now(),
                    }
                )
                continue
            try:
                item._verify_drive_item()
                item.sudo().write(
                    {
                        "reconciliation_state": "matched",
                        "storage_state": "available",
                        "last_error": False,
                    }
                )
            except Exception as error:
                safe_error = item.graph_connection_id._redact_text(str(error))[:2000]
                item.sudo().write(
                    {
                        "reconciliation_state": "failed",
                        "storage_state": "mismatch",
                        "last_error": safe_error,
                        "last_sync_at": fields.Datetime.now(),
                    }
                )
                item._enqueue("reconcile")
        return True

    def action_archive_remote(self):
        for item in self:
            item.check_linked_access("write")
            if item.sharepoint_item_id and item.storage_state not in ("deleted", "archived"):
                headers = {"If-Match": item.sharepoint_etag} if item.sharepoint_etag else None
                auth_context = "application" if item.env.su else "delegated"
                item.graph_connection_id.graph_request(
                    "DELETE",
                    (
                        f"/drives/{quote(item.sharepoint_drive_id)}/items/"
                        f"{quote(item.sharepoint_item_id)}"
                    ),
                    auth_context=auth_context,
                    user=item.env.user if auth_context == "delegated" else None,
                    headers=headers,
                    expected_statuses={204},
                )
            item.sudo().write(
                {
                    "storage_state": "archived",
                    "upload_state": "completed",
                    "active": False,
                    "last_sync_at": fields.Datetime.now(),
                }
            )
            item.message_post(body=_("Document moved to the SharePoint recycle bin."))
        return True

    def delegated_download_url(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        self.with_user(user).check_linked_access("read")
        if self.storage_state != "available":
            raise UserError(_("The document is not available in SharePoint."))
        payload = self.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}"
            ),
            auth_context="delegated",
            user=user,
            params={"$select": "id,name,size"},
        )
        if payload.get("id") != self.sharepoint_item_id:
            raise AccessError(_("SharePoint download validation failed."))
        url = payload.get("@microsoft.graph.downloadUrl")
        if not url or not str(url).startswith("https://"):
            raise UserError(_("SharePoint did not return a secure download URL."))
        return url

    def download_bytes(self, auth_context="delegated", user=None):
        self.ensure_one()
        user = user or self.env.user
        if auth_context == "delegated":
            self.with_user(user).check_linked_access("read")
        payload = self.graph_connection_id.graph_request(
            "GET",
            (
                f"/drives/{quote(self.sharepoint_drive_id)}/items/"
                f"{quote(self.sharepoint_item_id)}"
            ),
            auth_context=auth_context,
            user=user,
        )
        if payload.get("id") != self.sharepoint_item_id:
            raise UserError(_("SharePoint download verification failed."))
        download_url = payload.get("@microsoft.graph.downloadUrl")
        if not download_url:
            raise UserError(_("SharePoint did not return a valid download URL."))
        max_bytes = max(self.file_size * 2, 50 * 1024 * 1024) if self.file_size else (50 * 1024 * 1024)
        content = self.graph_connection_id.lhi_preauthenticated_download_request(
            download_url,
            auth_context=auth_context,
            user=user,
            maximum_bytes=max_bytes,
        )
        if self.file_size and len(content) != self.file_size:
            raise UserError(_("Downloaded SharePoint file size does not match metadata."))
        return content

    @api.model
    def cron_reconcile_documents(self, batch_size=100):
        documents = self.sudo().search(
            [("storage_state", "in", ("available", "missing", "mismatch"))],
            order="last_sync_at asc nulls first, id",
            limit=min(max(int(batch_size), 1), 500),
        )
        documents.action_reconcile()

    @api.model
    def cron_expire_upload_sessions(self, batch_size=100):
        now = fields.Datetime.now()
        documents = self.sudo().search(
            [
                ("upload_state", "in", ("session", "uploading")),
                ("upload_session_expiration", "<=", now),
            ],
            limit=min(max(int(batch_size), 1), 500),
        )
        for item in documents:
            if item.spool_path:
                item.sudo().write(
                    {
                        "upload_url": False,
                        "upload_session_expiration": False,
                        "upload_next_offset": 0,
                        "upload_state": "pending",
                        "storage_state": "pending",
                    }
                )
                item._enqueue("upload")
            else:
                item.sudo().write(
                    {
                        "upload_url": False,
                        "upload_state": "failed",
                        "storage_state": "failed",
                        "last_error": _("Browser upload session expired before confirmation."),
                    }
                )

    @api.model
    def cron_cleanup_orphan_spool(self, minimum_age_hours=24):
        directory = self._spool_directory()
        referenced = set(
            self.sudo().search([("spool_path", "!=", False)]).mapped("spool_path")
        )
        cutoff = time.time() - max(int(minimum_age_hours), 1) * 3600
        for entry in os.scandir(directory):
            if (
                not entry.is_file(follow_symlinks=False)
                or entry.path in referenced
                or entry.stat(follow_symlinks=False).st_mtime > cutoff
            ):
                continue
            try:
                os.unlink(entry.path)
            except OSError:
                pass

    @api.model
    def _lhi_prepare_and_confirm_memo_document(self, memo, docx_item, storage_policy):
        """Service contract v1 method for memo document conversion and SharePoint storage."""
        item = docx_item
        if not item or item.storage_state != "available":
            raise UserError(_("The Word document is not confirmed in SharePoint."))
        connection = item.graph_connection_id
        resource = f"/drives/{quote(item.sharepoint_drive_id)}/items/{quote(item.sharepoint_item_id)}"
        metadata = connection.graph_request(
            "GET",
            resource,
            auth_context="application",
            params={
                "$select": "id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,lastModifiedBy,parentReference,file"
            },
        )
        if metadata.get("id") != item.sharepoint_item_id:
            raise UserError(_("SharePoint returned a different Word DriveItem."))
        if not storage_policy:
            raise UserError(_("No SharePoint storage policy is configured for memos."))
        maximum_bytes = storage_policy.maximum_size_mb * 1024 * 1024

        docx_response = connection.lhi_binary_request(
            "GET", f"{resource}/content", auth_context="application", expected_statuses={200}, stream=True
        )
        docx_content = memo._bounded_response_content(docx_response, maximum_bytes) if hasattr(memo, "_bounded_response_content") else docx_response.content
        if not docx_content:
            raise UserError(_("SharePoint returned an empty Word document."))

        pdf_response = connection.lhi_binary_request(
            "GET", f"{resource}/content?format=pdf", auth_context="application", expected_statuses={200}, stream=True
        )
        pdf_content = memo._bounded_response_content(pdf_response, maximum_bytes) if hasattr(memo, "_bounded_response_content") else pdf_response.content
        if not pdf_content.startswith(b"%PDF"):
            raise UserError(_("Microsoft 365 did not return a valid PDF conversion."))

        pdf_hash = hashlib.sha256(pdf_content).hexdigest()
        pdf_item = self.create_from_bytes(
            name=f"{memo._safe_filename(memo.name) if hasattr(memo, '_safe_filename') else memo.name}-Submitted.pdf",
            content=pdf_content,
            mime_type="application/pdf",
            linked_model=memo._name,
            linked_record_id=memo.id,
            linked_field="source_pdf_item_id",
            requested_by=memo.requester_id,
            synchronous=True,
        )
        if pdf_item.storage_state != "available":
            raise UserError(_("SharePoint did not confirm the submitted memo PDF."))

        version = metadata.get("cTag") or metadata.get("eTag")
        return {
            "contract_version": self.MEMO_STORAGE_CONTRACT_VERSION,
            "document_item_id": pdf_item.id,
            "storage_state": pdf_item.storage_state,
            "content_hash": pdf_hash,
            "version": version or "",
        }
