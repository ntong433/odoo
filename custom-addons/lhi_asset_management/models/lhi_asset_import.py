# -*- coding: utf-8 -*-
import base64
import csv
import hashlib
import io
import json
import logging
import re
import time
from datetime import date, datetime
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:  # pragma: no cover - reported clearly when XLSX is selected
    openpyxl = None


HEADER_ALIASES = {
    "acquisition_type": {"type of acquisition"},
    "condition": {"asset condition"},
    "acquisition_date": {"date acquired"},
    "acquisition_source": {"acquisition source"},
    "project_abbreviation": {
        "project abbreviation",
        "project code",
    },
    "asset_value": {"purchase vaue", "purchase value"},
    "category": {"cat_cal", "asset category", "category", "category code"},
    "serial_number": {
        "asset sn",
        "asset serial number",
        "serial number",
    },
    "asset_tag": {"asset number"},
    "asset_name": {
        "asset name",
        "description",
        "item description",
        "asset description",
    },
    "state": {"state", "state code", "office location", "location"},
}

ACQUISITION_TYPES = {
    "purchased": "purchased",
    "purchase": "purchased",
    "donated": "donated",
    "donation": "donated",
    "partner contribution": "partner_contribution",
    "in-kind contribution": "in_kind",
    "in kind contribution": "in_kind",
    "transferred": "transferred",
    "transfer": "transferred",
    "leased in": "leased_in",
    "other": "other",
}


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _normalize_code(value):
    return (str(value or "")).strip().upper()


def _normalize_name(value):
    return " ".join(str(value or "").strip().split())


def _normalize_tag(tag):
    if not tag:
        return False
    tag_str = " ".join(str(tag).strip().split())
    return re.sub(r"\s*/\s*", "/", tag_str)


def _canonical_partner_key(name):
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s]", "", str(name)).casefold()
    return " ".join(cleaned.split())


class LhiAssetImportWizard(models.TransientModel):
    _name = "lhi.asset.import.wizard"
    _description = "Legacy Asset XLSX / CSV Import Wizard"

    upload = fields.Binary(string="Legacy Asset Register", required=True)
    filename = fields.Char(required=True)
    default_state_id = fields.Many2one(
        "res.country.state",
        string="Default Registration State",
        help="Used only when a row and its legacy tag do not identify a state.",
    )

    def _verify_and_confirm_asset_import_document(
        self, document, upload_payload, expected_size, expected_checksum
    ):
        """
        Perform bounded SharePoint DriveItem verification for Legacy Asset Import.
        Verifies returned DriveItem ID, remote size, conflict behavior, and logs safe diagnostic details.
        """
        if len(upload_payload) != expected_size:
            _logger.error(
                "Upload payload changed before transmission. Expected size: %s, payload size: %s",
                expected_size,
                len(upload_payload),
            )
            raise UserError(_("Upload payload changed before transmission."))

        upload_notice = False
        if document.storage_state != "available" and document.spool_path:
            try:
                document.action_upload()
            except UserError as err:
                upload_notice = err
                _logger.info(
                    "Initial upload notice for %s (Document %s): %s. Executing DriveItem metadata verification.",
                    document.name,
                    document.id,
                    err,
                )
            except Exception as err:
                _logger.error(
                    "Legacy Asset Import SharePoint upload failed. Document ID: %s, filename: %s, expected size: %s",
                    document.id,
                    document.name,
                    expected_size,
                )
                raise

        drive_id = document.sharepoint_drive_id
        returned_item_id = document.sharepoint_item_id
        connection = document.graph_connection_id

        if not drive_id or not returned_item_id:
            if upload_notice:
                _logger.error(
                    "Legacy Asset Import upload failed before SharePoint returned "
                    "a DriveItem. Document ID: %s, filename: %s, error: %s",
                    document.id,
                    document.name,
                    upload_notice,
                )
                document._mark_failed(str(upload_notice), enqueue=False)
                raise upload_notice

            _logger.error(
                "Remote item is missing after upload completion. Document ID: %s, filename: %s, expected size: %s",
                document.id,
                document.name,
                expected_size,
            )
            document._mark_failed(
                "Remote item is missing after upload completion.",
                enqueue=False,
            )
            raise UserError(_("Remote item is missing after upload completion."))

        if document.sharepoint_item_id and returned_item_id != document.sharepoint_item_id:
            _logger.error(
                "Returned DriveItem ID differs from the persisted item ID. Persisted: %s, Returned: %s",
                document.sharepoint_item_id,
                returned_item_id,
            )
            raise UserError(_("Returned DriveItem ID differs from the persisted item ID."))

        max_retries = 5
        remote_size = -1
        last_metadata = {}

        for attempt in range(max_retries):
            try:
                last_metadata = connection.graph_request(
                    "GET",
                    f"/drives/{quote(drive_id)}/items/{quote(returned_item_id)}",
                    auth_context="application",
                    params={"$select": "id,name,size,eTag,file"},
                )
                if last_metadata and isinstance(last_metadata, dict):
                    meta_id = last_metadata.get("id")
                    if meta_id != returned_item_id:
                        _logger.error(
                            "SharePoint returned metadata for a different file. Persisted ID: %s, returned ID: %s",
                            returned_item_id,
                            meta_id,
                        )
                        raise UserError(_("SharePoint returned metadata for a different file."))

                    remote_size = int(last_metadata.get("size") or 0)
                    if remote_size == expected_size:
                        break
            except UserError:
                raise
            except Exception as exc:
                _logger.warning(
                    "Attempt %s/%s fetching DriveItem %s metadata failed: %s",
                    attempt + 1,
                    max_retries,
                    returned_item_id,
                    exc,
                )

            if attempt < max_retries - 1:
                time.sleep(0.5)

        if last_metadata and last_metadata.get("id") and last_metadata.get("id") != returned_item_id:
            raise UserError(_("SharePoint returned metadata for a different file."))

        if remote_size < 0 or not last_metadata:
            _logger.error(
                "Remote item is missing after upload completion. Document ID: %s, Item ID: %s",
                document.id,
                returned_item_id,
            )
            document._mark_failed("Remote item is missing after upload completion.", enqueue=False)
            raise UserError(_("Remote item is missing after upload completion."))

        conflict_behavior = document.storage_policy_id.conflict_behavior or "default"
        final_remote_name = last_metadata.get("name") or document.name
        checksum_prefix = expected_checksum[:8] if expected_checksum else ""
        is_xlsx = (final_remote_name or "").lower().endswith(".xlsx")

        if remote_size != expected_size and not is_xlsx:
            _logger.error(
                "Legacy Asset Import remote size differs from exact uploaded payload. "
                "Original decoded size: %s, upload payload size: %s, SHA-256 prefix: %s, "
                "returned DriveItem ID: %s, stored document ID: %s, remote size: %s, "
                "final remote filename: %s, conflict behavior: %s",
                expected_size,
                len(upload_payload),
                checksum_prefix,
                returned_item_id,
                document.id,
                remote_size,
                final_remote_name,
                conflict_behavior,
            )
            document._mark_failed("Remote size differs from the exact uploaded payload.", enqueue=False)
            raise UserError(
                _("Remote size differs from the exact uploaded payload. Expected %s bytes, remote SharePoint size %s bytes.")
                % (expected_size, remote_size)
            )

        if remote_size != expected_size and is_xlsx:
            _logger.info(
                "SharePoint transformed Legacy Asset Import XLSX after upload. "
                "Original size: %s, remote size: %s, DriveItem ID: %s.",
                expected_size,
                remote_size,
                returned_item_id,
            )

            # SharePoint may rewrite an Office XLSX package. Verify the
            # actual final remote content instead of requiring its byte size
            # to remain identical to the original upload.
            document.sudo().write({"file_size": remote_size})

            try:
                document._calculate_remote_hashes(
                    auth_context="application",
                    user=self.env.user,
                )
                document._verify_drive_item(
                    auth_context="application",
                    user=self.env.user,
                )
            except Exception:
                document._mark_failed(
                    "Final SharePoint XLSX verification failed.",
                    enqueue=False,
                )
                raise

        _logger.info(
            "Legacy Asset Import SharePoint verification succeeded. "
            "Original decoded size: %s, upload payload size: %s, SHA-256 prefix: %s, "
            "returned DriveItem ID: %s, stored document ID: %s, remote size: %s, "
            "final remote filename: %s, conflict behavior: %s",
            expected_size,
            len(upload_payload),
            checksum_prefix,
            returned_item_id,
            document.id,
            remote_size,
            final_remote_name,
            conflict_behavior,
        )

        document.sudo().write(
            {
                "name": final_remote_name,
                "file_size": remote_size,
                "sharepoint_etag": last_metadata.get("eTag") or document.sharepoint_etag,
                "storage_state": "available",
                "upload_state": "completed",
                "reconciliation_state": "matched",
                "last_error": False,
            }
        )
        return True

    def action_preview(self):
        self.ensure_one()
        if not self.env.user.has_group("lhi_security.group_lhi_asset_officer"):
            raise AccessError(_("Only Asset Officers may import asset registers."))
        filename = self.filename or ""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in ("csv", "xlsx"):
            raise ValidationError(_("Upload a .csv or .xlsx asset register."))

        decoded_content = base64.b64decode(self.upload or b"")
        if not decoded_content:
            raise ValidationError(_("The uploaded asset register is empty."))

        upload_payload = decoded_content
        expected_size = len(upload_payload)
        expected_checksum = hashlib.sha256(upload_payload).hexdigest()

        batch = self.env["lhi.asset.import.batch"].create(
            {
                "source_filename": filename,
                "default_state_id": self.default_state_id.id,
            }
        )

        # Each legacy import batch must keep its own immutable source file in
        # SharePoint. The original user filename remains on source_filename,
        # while the remote document name is made unique per audit batch.
        if "." in filename:
            filename_stem, filename_extension = filename.rsplit(".", 1)
            remote_filename = "%s__%s.%s" % (
                filename_stem,
                (batch.name or ("batch-%s" % batch.id)).replace("/", "-"),
                filename_extension,
            )
        else:
            remote_filename = "%s__%s" % (
                filename,
                (batch.name or ("batch-%s" % batch.id)).replace("/", "-"),
            )

        # Parse preview independently from an in-memory copy without mutating upload_payload
        preview_stream = io.BytesIO(bytes(decoded_content))
        batch._load_preview(preview_stream, extension)

        mime_type = (
            "text/csv"
            if extension == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        idempotency_key = self.env["lhi.document.item"]._make_idempotency_key(
            batch._name, batch.id, "source_file", filename, expected_checksum
        )
        existing_doc = self.env["lhi.document.item"].sudo().search(
            [("idempotency_key", "=", idempotency_key)], limit=1
        )
        if existing_doc:
            if existing_doc.checksum == expected_checksum and existing_doc.file_size == expected_size:
                document = existing_doc
            else:
                existing_doc._mark_failed("Payload mismatch on retry", enqueue=False)
                document = self.env["lhi.document.item"].create_from_bytes(
                    name=remote_filename,
                    content=upload_payload,
                    mime_type=mime_type,
                    linked_model=batch._name,
                    linked_record_id=batch.id,
                    linked_field="source_file",
                    requested_by=self.env.user,
                    synchronous=False,
                )
        else:
            document = self.env["lhi.document.item"].create_from_bytes(
                name=remote_filename,
                content=upload_payload,
                mime_type=mime_type,
                linked_model=batch._name,
                linked_record_id=batch.id,
                linked_field="source_file",
                requested_by=self.env.user,
                synchronous=False,
            )

        self._verify_and_confirm_asset_import_document(
            document=document,
            upload_payload=upload_payload,
            expected_size=expected_size,
            expected_checksum=expected_checksum,
        )

        batch.sudo().with_context(lhi_asset_import_system=True).write(
            {
                "source_document_item_id": document.id,
                "source_sharepoint_item_id": document.sharepoint_item_id,
                "source_checksum": document.checksum,
                "source_storage_state": (
                    "available"
                    if document.storage_state == "available"
                    else "failed"
                ),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Asset Import Batch"),
            "res_model": batch._name,
            "res_id": batch.id,
            "view_mode": "form",
            "target": "current",
        }


class LhiAssetImportBatch(models.Model):
    _name = "lhi.asset.import.batch"
    _description = "Auditable Legacy Asset Import Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("New"), copy=False)
    source_filename = fields.Char(required=True, readonly=True)
    source_document_item_id = fields.Many2one(
        "lhi.document.item",
        readonly=True,
        ondelete="restrict",
        copy=False,
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    error_report_document_item_id = fields.Many2one(
        "lhi.document.item",
        readonly=True,
        ondelete="restrict",
        copy=False,
        groups="lhi_security.group_lhi_erp_admin,lhi_security.group_lhi_integration_service",
    )
    source_sharepoint_item_id = fields.Char(readonly=True, copy=False)
    source_checksum = fields.Char(string="Source SHA-256", readonly=True, copy=False)
    source_storage_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("available", "Available"),
            ("failed", "Failed"),
        ],
        readonly=True,
        copy=False,
    )
    error_report_checksum = fields.Char(readonly=True, copy=False)
    default_state_id = fields.Many2one("res.country.state")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("imported", "Imported"),
            ("partial", "Partially Imported"),
            ("rolled_back", "Rolled Back"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "lhi.asset.import.row", "batch_id", string="Preview Rows", copy=False
    )
    imported_row_count = fields.Integer(readonly=True)
    rejected_row_count = fields.Integer(readonly=True)
    duplicate_count = fields.Integer(readonly=True)

    created_category_count = fields.Integer(readonly=True)
    reused_category_count = fields.Integer(readonly=True)
    created_project_count = fields.Integer(readonly=True)
    reused_project_count = fields.Integer(readonly=True)
    created_partner_count = fields.Integer(readonly=True)
    reused_partner_count = fields.Integer(readonly=True)

    total_imported_value = fields.Monetary(
        readonly=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    imported_by_id = fields.Many2one("res.users", readonly=True)
    imported_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("lhi.asset.import.batch")
                    or _("New")
                )
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("lhi_asset_import_system"):
            return super().write(vals)
        protected = {
            "source_filename",
            "source_document_item_id",
            "error_report_document_item_id",
            "source_sharepoint_item_id",
            "source_checksum",
            "source_storage_state",
            "error_report_checksum",
            "state",
            "imported_row_count",
            "rejected_row_count",
            "duplicate_count",
            "created_category_count",
            "reused_category_count",
            "created_project_count",
            "reused_project_count",
            "created_partner_count",
            "reused_partner_count",
            "total_imported_value",
            "imported_by_id",
            "imported_at",
        }
        if protected.intersection(vals):
            raise AccessError(_("Use the import batch actions to update protected fields."))
        if any(batch.state != "draft" for batch in self):
            raise ValidationError(_("Only draft import batches can be edited."))
        return super().write(vals)

    @api.model
    def _normalise_header(self, value):
        return " ".join(str(value or "").strip().casefold().split())

    def _canonical_header(self, value):
        normalised = self._normalise_header(value)
        for canonical, aliases in HEADER_ALIASES.items():
            if normalised in aliases:
                return canonical
        return False

    def _csv_rows(self, content):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValidationError(_("CSV files must use UTF-8 encoding.")) from error
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValidationError(_("The CSV file has no header row."))
        return list(reader), reader.fieldnames

    def _xlsx_rows(self, content):
        if openpyxl is None:
            raise UserError(
                _("The openpyxl Python package is required for XLSX asset imports.")
            )
        try:
            workbook = openpyxl.load_workbook(
                io.BytesIO(content), read_only=True, data_only=True
            )
        except Exception as error:
            raise ValidationError(_("The XLSX workbook could not be read.")) from error
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        try:
            headers = [str(value or "") for value in next(iterator)]
        except StopIteration as error:
            raise ValidationError(_("The XLSX workbook is empty.")) from error
        rows = [
            {headers[index]: value for index, value in enumerate(values)}
            for values in iterator
            if any(value not in (None, "") for value in values)
        ]
        workbook.close()
        return rows, headers

    def _load_preview(self, content, extension):
        self.ensure_one()
        if self.state != "draft" or self.line_ids:
            raise UserError(_("This batch preview has already been loaded."))
        raw_bytes = content.read() if hasattr(content, "read") else bytes(content)
        rows, headers = (
            self._csv_rows(raw_bytes)
            if extension == "csv"
            else self._xlsx_rows(raw_bytes)
        )
        mapped_headers = {
            header: self._canonical_header(header)
            for header in headers
            if self._canonical_header(header)
        }
        if not mapped_headers:
            raise ValidationError(
                _("None of the supported legacy asset headers were found.")
            )
        line_values = []
        for number, raw in enumerate(rows, start=2):
            canonical = {}
            extras = {}
            for header, value in raw.items():
                mapped = mapped_headers.get(header)
                if mapped:
                    canonical[mapped] = value
                else:
                    extras[str(header)] = value
            line_values.append(
                self._prepare_row_values(number, canonical, extras, raw)
            )
        if not line_values:
            raise ValidationError(_("The asset register contains no data rows."))
        self.env["lhi.asset.import.row"].create(line_values)
        self.message_post(
            body=_("Loaded %s legacy asset rows for preview.") % len(line_values)
        )

    def _prepare_row_values(self, number, values, extras, raw):
        exact_tag = values.get("asset_tag")
        if exact_tag not in (None, ""):
            exact_tag = str(exact_tag).strip()
        else:
            exact_tag = False
        serial = values.get("serial_number")
        serial = str(serial).strip() if serial not in (None, "") else False
        name = values.get("asset_name")
        name = str(name).strip() if name not in (None, "") else False
        if not name:
            name = exact_tag or serial or _("Imported Asset Row %s") % number
        return {
            "batch_id": self.id,
            "row_number": number,
            "raw_values_json": json.dumps(raw, default=_json_default, ensure_ascii=False),
            "extra_values_json": json.dumps(
                extras, default=_json_default, ensure_ascii=False
            ),
            "asset_name": name,
            "asset_tag": exact_tag,
            "serial_number": serial,
            "acquisition_type_text": str(
                values.get("acquisition_type") or ""
            ).strip(),
            "condition_text": str(values.get("condition") or "").strip(),
            "acquisition_date_text": (
                values.get("acquisition_date").isoformat()
                if isinstance(values.get("acquisition_date"), (date, datetime))
                else str(values.get("acquisition_date") or "").strip()
            ),
            "acquisition_source_text": str(
                values.get("acquisition_source") or ""
            ).strip(),
            "project_abbreviation": str(
                values.get("project_abbreviation") or ""
            ).strip(),
            "asset_value_text": str(values.get("asset_value") or "").strip(),
            "category_text": str(values.get("category") or "").strip(),
            "state_text": str(values.get("state") or "").strip(),
        }

    def _reconcile_master_data(self):
        self.ensure_one()
        created_cat = 0
        reused_cat = 0
        created_proj = 0
        reused_proj = 0
        created_part = 0
        reused_part = 0

        cat_cache = {}
        proj_cache = {}
        part_cache = {}

        for row in self.line_ids:
            # 1. Category Reconciliation
            raw_cat = (row.category_text or "").strip()
            if raw_cat:
                cat_code = _normalize_code(raw_cat)
                cat_name = _normalize_name(raw_cat)
                if cat_code:
                    category = cat_cache.get(cat_code)
                    if not category:
                        category = self.env["lhi.asset.category"].search(
                            [("code", "=ilike", cat_code)], limit=1
                        )
                        if category:
                            reused_cat += 1
                            if cat_name and (
                                not category.name or category.name.strip().upper() == cat_code
                            ):
                                category.write({"name": cat_name})
                        else:
                            category = self.env["lhi.asset.category"].create({
                                "code": cat_code,
                                "name": cat_name or cat_code,
                                "company_id": self.company_id.id,
                            })
                            created_cat += 1
                        cat_cache[cat_code] = category
                    row.category_id = category.id

            # 2. Project Code Reconciliation
            raw_proj = (row.project_abbreviation or "").strip()
            if raw_proj:
                proj_code = _normalize_code(raw_proj)
                if proj_code:
                    project = proj_cache.get(proj_code)
                    if not project:
                        project = self.env["lhi.project"].search(
                            [("code", "=ilike", proj_code)], limit=1
                        )
                        if project:
                            reused_proj += 1
                        else:
                            project = self.env["lhi.project"].create({
                                "code": proj_code,
                                "name": proj_code,
                                "company_id": self.company_id.id,
                            })
                            created_proj += 1
                        proj_cache[proj_code] = project
                    row.project_id = project.id

            # 3. Vendor / Acquisition Source Reconciliation
            raw_src = (row.acquisition_source_text or "").strip()
            if raw_src:
                norm_src = _normalize_name(raw_src)
                can_key = _canonical_partner_key(raw_src)
                if can_key:
                    partner = part_cache.get(can_key)
                    if not partner:
                        partner = self.env["res.partner"].search(
                            [("name", "=ilike", norm_src)], limit=1
                        )
                        if not partner:
                            all_partners = self.env["res.partner"].search([])
                            for p in all_partners:
                                if _canonical_partner_key(p.name) == can_key:
                                    partner = p
                                    break
                        if partner:
                            reused_part += 1
                        else:
                            partner_vals = {
                                "name": norm_src,
                            }
                            if "supplier_rank" in self.env["res.partner"]._fields:
                                partner_vals["supplier_rank"] = 1
                            partner = self.env["res.partner"].create(partner_vals)
                            created_part += 1
                        part_cache[can_key] = partner
                    row.acquisition_source_id = partner.id

            # 4. Registration State Resolution
            state = False
            if row.state_text:
                norm_st = _normalize_name(row.state_text)
                state = self.env["res.country.state"].search(
                    [
                        "|", "|",
                        ("lhi_asset_code", "=ilike", norm_st),
                        ("code", "=ilike", norm_st),
                        ("name", "=ilike", norm_st),
                    ],
                    limit=1,
                )
            if not state and row.asset_tag:
                parsed = self.env["lhi.asset.tag.rule"].parse_tag(row.asset_tag)
                if parsed and parsed.get("state"):
                    st_code = parsed["state"]
                    state = self.env["res.country.state"].search(
                        [
                            "|",
                            ("lhi_asset_code", "=ilike", st_code),
                            ("code", "=ilike", st_code),
                        ],
                        limit=1,
                    )
            state = state or self.default_state_id
            if state:
                row.registration_state_id = state.id

        self.with_context(lhi_asset_import_system=True).write({
            "created_category_count": created_cat,
            "reused_category_count": reused_cat,
            "created_project_count": created_proj,
            "reused_project_count": reused_proj,
            "created_partner_count": created_part,
            "reused_partner_count": reused_part,
        })

    def action_validate(self):
        for batch in self:
            if batch.state != "draft":
                raise UserError(_("Only draft batches can be validated."))

            # Reconcile Categories, Projects, Vendors, and Registration States
            batch._reconcile_master_data()

            seen_serials = {}
            seen_tags = {}

            duplicates = 0
            rejected = 0

            for row in batch.line_ids:
                row._validate_row(seen_serials=seen_serials, seen_tags=seen_tags)
                duplicates += int(row.is_duplicate)
                rejected += int(row.validation_state == "error")

            batch.with_context(lhi_asset_import_system=True).write(
                {
                    "state": "validated",
                    "duplicate_count": duplicates,
                    "rejected_row_count": rejected,
                }
            )

            batch.message_post(
                body=_(
                    "Master data reconciliation complete: "
                    "Categories (%(cat_c)s created, %(cat_r)s reused), "
                    "Projects (%(proj_c)s created, %(proj_r)s reused), "
                    "Vendors (%(part_c)s created, %(part_r)s reused). "
                    "Validation summary: %(dup)s duplicates, %(rej)s rejected rows."
                )
                % {
                    "cat_c": batch.created_category_count,
                    "cat_r": batch.reused_category_count,
                    "proj_c": batch.created_project_count,
                    "proj_r": batch.reused_project_count,
                    "part_c": batch.created_partner_count,
                    "part_r": batch.reused_partner_count,
                    "dup": duplicates,
                    "rej": rejected,
                }
            )
        return True

    def action_return_to_draft(self):
        for batch in self:
            if batch.state != "validated":
                raise UserError(_("Only validated batches can return to draft."))
            batch.line_ids.write(
                {
                    "validation_state": "draft",
                    "error_message": False,
                    "is_duplicate": False,
                }
            )
            batch.with_context(lhi_asset_import_system=True).write({"state": "draft"})
        return True

    def action_import(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_officer"):
            raise AccessError(_("Only Asset Officers may import validated rows."))
        for batch in self:
            if batch.state != "validated":
                raise UserError(_("Validate the batch before importing it."))
            imported = 0
            total = 0.0
            for row in batch.line_ids.filtered(
                lambda item: item.validation_state == "valid"
            ):
                try:
                    with self.env.cr.savepoint():
                        asset = row._create_asset()
                        row.write(
                            {
                                "asset_id": asset.id,
                                "validation_state": "imported",
                                "error_message": False,
                            }
                        )
                        imported += 1
                        total += asset.asset_value
                except Exception as error:
                    row.write(
                        {
                            "validation_state": "error",
                            "error_message": str(error),
                        }
                    )
            rejected = len(
                batch.line_ids.filtered(lambda item: item.validation_state == "error")
            )
            target_state = "imported" if not rejected else "partial"
            batch.with_context(lhi_asset_import_system=True).write(
                {
                    "state": target_state,
                    "imported_row_count": imported,
                    "rejected_row_count": rejected,
                    "total_imported_value": total,
                    "imported_by_id": self.env.user.id,
                    "imported_at": fields.Datetime.now(),
                }
            )
            batch.message_post(
                body=_(
                    "Import reconciled: %(imported)s imported, %(rejected)s "
                    "rejected, operational value %(value)s."
                )
                % {"imported": imported, "rejected": rejected, "value": total}
            )
        return True

    def action_download_source(self):
        self.ensure_one()
        document = self.sudo().source_document_item_id
        if not document:
            raise UserError(_("No preserved source document is available."))
        return {
            "type": "ir.actions.act_url",
            "url": "/lhi/sharepoint/document/%s/download"
            % document.uuid,
            "target": "new",
        }

    def action_download_error_report(self):
        self.ensure_one()
        error_rows = self.line_ids.filtered(
            lambda item: item.validation_state == "error"
        )
        if not error_rows:
            raise UserError(_("This import batch has no rejected rows."))
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Row", "Asset Number", "Serial Number", "Error"])
        for row in error_rows:
            writer.writerow(
                [
                    row.row_number,
                    row.asset_tag or "",
                    row.serial_number or "",
                    row.error_message or "",
                ]
            )
        content = output.getvalue().encode("utf-8-sig")
        filename = "%s-errors.csv" % self.name.replace("/", "-")
        document = self.env["lhi.document.item"].create_from_bytes(
            name=filename,
            content=content,
            mime_type="text/csv",
            linked_model=self._name,
            linked_record_id=self.id,
            linked_field="error_report",
            requested_by=self.env.user,
            synchronous=True,
        )
        self.sudo().with_context(lhi_asset_import_system=True).write(
            {
                "error_report_document_item_id": document.id,
                "error_report_checksum": document.checksum,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/lhi/sharepoint/document/%s/download" % document.uuid,
            "target": "new",
        }

    def action_rollback(self):
        if not self.env.user.has_group("lhi_security.group_lhi_asset_manager"):
            raise AccessError(_("Only Asset Managers may roll back an import batch."))
        for batch in self:
            if batch.state not in ("imported", "partial"):
                raise UserError(_("Only imported batches can be rolled back."))
            assets = batch.line_ids.mapped("asset_id").exists()
            for asset in assets:
                downstream = (
                    asset.transfer_ids
                    or asset.retag_request_ids
                    or asset.history_ids.filtered(
                        lambda event: event.event_type
                        not in (
                            "acquisition",
                            "registration",
                            "tagging",
                            "status",
                            "import",
                        )
                    )
                )
                if downstream:
                    raise ValidationError(
                        _(
                            "Asset %s has downstream lifecycle transactions; "
                            "the import cannot be rolled back."
                        )
                        % asset.display_name
                    )
            assets.mapped("history_ids").with_context(
                lhi_asset_import_rollback=True
            ).unlink()
            assets.with_context(lhi_asset_import_rollback=True).unlink()
            batch.line_ids.write(
                {"asset_id": False, "validation_state": "rolled_back"}
            )
            batch.with_context(lhi_asset_import_system=True).write(
                {"state": "rolled_back"}
            )
            batch.message_post(body=_("Imported assets were rolled back."))
        return True

    def unlink(self):
        if any(
            batch.state != "draft" or batch.sudo().source_document_item_id
            for batch in self
        ):
            raise ValidationError(_("Audited import batches cannot be deleted."))
        return super().unlink()


class LhiAssetImportRow(models.Model):
    _name = "lhi.asset.import.row"
    _description = "Legacy Asset Import Preview Row"
    _order = "row_number, id"

    batch_id = fields.Many2one(
        "lhi.asset.import.batch", required=True, ondelete="cascade", index=True
    )
    row_number = fields.Integer(required=True)
    raw_values_json = fields.Text(readonly=True)
    extra_values_json = fields.Text(readonly=True)
    asset_name = fields.Char(required=True)
    asset_tag = fields.Char(string="Asset Number")
    serial_number = fields.Char(string="Manufacturer Serial Number")
    acquisition_type_text = fields.Char(string="Type of Acquisition")
    condition_text = fields.Char(string="Asset Condition")
    acquisition_date_text = fields.Char(string="Date Acquired")
    acquisition_source_text = fields.Char(string="Acquisition Source")
    project_abbreviation = fields.Char()
    asset_value_text = fields.Char(string="Purchase Value")
    category_text = fields.Char(string="Category / cat_cal")
    state_text = fields.Char()

    acquisition_type = fields.Selection(
        selection=lambda self: self.env["lhi.asset"]._fields[
            "acquisition_type"
        ].selection
    )
    acquisition_date = fields.Date()
    acquisition_source_id = fields.Many2one("res.partner")
    project_id = fields.Many2one("lhi.project")
    category_id = fields.Many2one("lhi.asset.category")
    condition_id = fields.Many2one("lhi.asset.condition")
    registration_state_id = fields.Many2one("res.country.state")
    asset_value = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="batch_id.currency_id")
    validation_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("valid", "Valid"),
            ("error", "Error"),
            ("imported", "Imported"),
            ("rolled_back", "Rolled Back"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    error_message = fields.Text(readonly=True)
    is_duplicate = fields.Boolean(readonly=True)
    asset_id = fields.Many2one("lhi.asset", readonly=True, ondelete="set null")

    _batch_row_unique = models.Constraint(
        "unique(batch_id, row_number)", "Import row numbers must be unique per batch."
    )

    def write(self, vals):
        editable = {
            "asset_name",
            "asset_tag",
            "serial_number",
            "acquisition_type_text",
            "condition_text",
            "acquisition_date_text",
            "acquisition_source_text",
            "project_abbreviation",
            "asset_value_text",
            "category_text",
            "state_text",
        }
        if editable.intersection(vals) and any(
            row.batch_id.state != "draft" for row in self
        ):
            raise ValidationError(_("Rows can only be corrected while the batch is draft."))
        return super().write(vals)

    def _parse_date(self, value):
        value = (value or "").strip()
        if not value:
            return False
        for format_string in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value[:10], format_string).date()
            except ValueError:
                continue
        raise ValidationError(_("Invalid acquisition date '%s'.") % value)

    def _resolve_named(self, model_name, value, fields_to_match):
        if not value:
            return self.env[model_name]
        domain = []
        for index, field_name in enumerate(fields_to_match):
            if index:
                domain.insert(0, "|")
            domain.append((field_name, "=ilike", value))
        return self.env[model_name].search(domain, limit=1)

    def _validate_row(self, seen_serials=None, seen_tags=None):
        self.ensure_one()
        errors = []
        duplicate = False

        if seen_serials is None:
            seen_serials = {}
        if seen_tags is None:
            seen_tags = {}

        acquisition_type = ACQUISITION_TYPES.get(
            (self.acquisition_type_text or "").strip().casefold()
        )
        if self.acquisition_type_text and not acquisition_type:
            errors.append(_("Unknown acquisition type '%s'.") % self.acquisition_type_text)

        try:
            acquisition_date = self._parse_date(self.acquisition_date_text)
        except ValidationError as error:
            acquisition_date = False
            errors.append(str(error))

        try:
            asset_value = (
                float((self.asset_value_text or "").replace(",", ""))
                if self.asset_value_text
                else 0.0
            )
            if asset_value < 0:
                raise ValueError()
        except ValueError:
            asset_value = 0.0
            errors.append(_("Purchase Value must be a non-negative number."))

        if self.project_abbreviation and not self.project_id:
            errors.append(_("Unknown project abbreviation '%s'.") % self.project_abbreviation)
        if not self.category_id:
            errors.append(_("Unknown or missing asset category '%s'.") % self.category_text)
        condition = self._resolve_named(
            "lhi.asset.condition", self.condition_text, ("code", "name")
        )
        if not condition:
            errors.append(_("Unknown or missing asset condition '%s'.") % self.condition_text)
        if self.acquisition_source_text and not self.acquisition_source_id:
            errors.append(_("Unknown acquisition source '%s'.") % self.acquisition_source_text)

        if not self.registration_state_id:
            errors.append(_("A registration state or batch default state is required."))

        # Asset Tag Duplicate Check
        if self.asset_tag:
            norm_tag = _normalize_tag(self.asset_tag)
            if norm_tag in seen_tags:
                first_row = seen_tags[norm_tag]
                duplicate = True
                errors.append(
                    _("Asset Number is duplicated within this batch. First occurrence: row %s.") % first_row
                )
            else:
                seen_tags[norm_tag] = self.row_number

            if self.env["lhi.asset"].search_count([("asset_tag", "=ilike", norm_tag)]):
                duplicate = True
                errors.append(_("Duplicate Asset Number '%s'.") % self.asset_tag)

        # Serial Number Duplicate Check
        raw_serial = (self.serial_number or "").strip()
        if raw_serial:
            norm_serial = " ".join(raw_serial.split()).casefold()
            serial_scope = (
                self.registration_state_id.id or False,
                norm_serial,
            )

            if serial_scope in seen_serials:
                first_row = seen_serials[serial_scope]
                duplicate = True
                errors.append(
                    _(
                        "Serial number is duplicated within this registration "
                        "state in the current batch. First occurrence: row %s."
                    )
                    % first_row
                )
            else:
                seen_serials[serial_scope] = self.row_number

            if self.env["lhi.asset"].search_count(
                [
                    ("serial_number", "=ilike", raw_serial),
                    ("company_id", "=", self.batch_id.company_id.id),
                    (
                        "registration_state_id",
                        "=",
                        self.registration_state_id.id,
                    ),
                ]
            ):
                duplicate = True
                errors.append(
                    _(
                        "Duplicate serial number '%s' in registration state '%s'."
                    )
                    % (
                        raw_serial,
                        self.registration_state_id.display_name,
                    )
                )

        self.write(
            {
                "acquisition_type": acquisition_type,
                "acquisition_date": acquisition_date,
                "condition_id": condition.id if condition else False,
                "asset_value": asset_value,
                "validation_state": "error" if (errors or duplicate) else "valid",
                "error_message": "\n".join(errors) if errors else False,
                "is_duplicate": duplicate,
            }
        )

    def _create_asset(self):
        self.ensure_one()
        if self.validation_state != "valid":
            raise ValidationError(_("Only valid preview rows can be imported."))
        asset = self.env["lhi.asset"].create(
            {
                "name": self.asset_name,
                "asset_tag": self.asset_tag or False,
                "serial_number": self.serial_number,
                "category_id": self.category_id.id,
                "condition_id": self.condition_id.id,
                "acquisition_date": self.acquisition_date,
                "acquisition_type": self.acquisition_type,
                "acquisition_source_id": self.acquisition_source_id.id,
                "legal_owner_id": self.batch_id.company_id.partner_id.id,
                "project_id": self.project_id.id,
                "project_abbreviation": self.project_abbreviation,
                "registration_state_id": self.registration_state_id.id,
                "state_id": self.registration_state_id.id,
                "asset_value": self.asset_value,
                "value_source": "legacy",
                "value_date": self.acquisition_date or fields.Date.context_today(self),
                "currency_id": self.currency_id.id,
                "import_batch_id": self.batch_id.id,
                "company_id": self.batch_id.company_id.id,
            }
        )
        asset.action_confirm()
        asset._lhi_add_history(
            "import",
            _("Imported from legacy batch %s, source row %s.")
            % (self.batch_id.name, self.row_number),
            reference_model=self.batch_id._name,
            reference_id=self.batch_id.id,
        )
        return asset
