"""
LHI Memo Document Gateway
=========================
Mediates all access from Memo business logic to ``lhi.document.item`` records.

A normal Memo user (``lhi_employee``) has **no** ACL on ``lhi.document.item``.
This gateway enforces a strict six-step authorization sequence before any
privileged elevation, then returns only safe scalar contracts — never a
live ORM recordset — back to the caller.

Contract version: MEMO_DOCUMENT_CONTRACT_VERSION = 1
"""
import hashlib
import logging
import uuid
from urllib.parse import quote

from odoo.exceptions import AccessError, UserError
from odoo import _


_logger = logging.getLogger(__name__)

MEMO_DOCUMENT_CONTRACT_VERSION = 1

ALLOWED_LINKED_FIELDS = frozenset(
    {
        "source_docx_item_id",
        "source_pdf_item_id",
        "signed_pdf_item_id",
        "certificate_item_id",
    }
)


class MemoDocumentGateway:
    """
    Server-side gateway owning all Memo-to-SharePoint document operations.

    Instantiate once per action invocation::

        gateway = MemoDocumentGateway(env, memo, env.user)

    All public methods return safe scalar dictionaries conforming to
    MEMO_DOCUMENT_CONTRACT_VERSION.  They never return a live
    ``lhi.document.item`` recordset to the caller.
    """

    def __init__(self, env, memo, calling_user):
        self._env = env
        self._memo = memo
        self._calling_user = calling_user

    # ------------------------------------------------------------------ #
    # Authorization                                                        #
    # ------------------------------------------------------------------ #

    def _is_authorized_caller(self):
        """Return True if the calling user is a permitted workflow participant."""
        memo = self._memo
        user = self._calling_user

        if user.has_group("lhi_memo_management.group_lhi_memo_admin"):
            return True
        if user.has_group("lhi_security.group_lhi_erp_admin"):
            return True
        if memo.requester_id == user:
            return True
        if user in memo.preparation_officer_ids:
            return True
        # Active approver
        sig = memo.sudo().signature_request_id
        if sig and sig.current_recipient_id and sig.current_recipient_id.user_id == user:
            return True
        # Any active approver line
        active_lines = memo.sudo().approver_line_ids.filtered(
            lambda line: line.state in ("pending", "approved")
            and line.approver_user_id == user
        )
        if active_lines:
            return True
        return False

    def _authorize_and_fetch_item(self, field_name):
        """
        Perform the full six-step authorization sequence and return the
        sudoed ``lhi.document.item`` record.

        Steps:
        1. ``field_name`` must be in ALLOWED_LINKED_FIELDS.
        2. Calling user must be an authorized workflow participant.
        3. Fetch item via ``memo.sudo().<field_name>``.
        4. Confirm ``item.linked_model == "lhi.memo"``.
        5. Confirm ``item.linked_record_id == memo.id``.
        6. Confirm ``item.company_id == memo.company_id``.
        """
        if field_name not in ALLOWED_LINKED_FIELDS:
            raise AccessError(
                _("Document field '%(field)s' is not a permitted gateway target.")
                % {"field": field_name}
            )

        if not self._is_authorized_caller():
            raise AccessError(
                _(
                    "Only the requester, preparation officer, active approver, "
                    "or administrator may access Memo documents."
                )
            )

        # Privileged fetch — memo.sudo() then field access
        memo_sudo = self._memo.sudo()
        item = getattr(memo_sudo, field_name)

        if not item:
            raise UserError(
                _("No document is linked to field '%(field)s' for this memo.")
                % {"field": field_name}
            )

        # Step 4: linkage model guard
        if item.linked_model != "lhi.memo":
            raise AccessError(
                _("The linked document does not belong to the Memo model.")
            )
        # Step 5: record guard
        if item.linked_record_id != self._memo.id:
            raise AccessError(
                _("The linked document does not belong to this memo.")
            )
        # Step 6: company guard
        if item.company_id != self._memo.company_id:
            raise AccessError(
                _("The linked document belongs to a different company.")
            )

        return item  # still sudoed; never returned to caller

    # ------------------------------------------------------------------ #
    # Public contract methods                                             #
    # ------------------------------------------------------------------ #

    def read_document_metadata(self, field_name):
        """
        Read storage metadata for the document linked to ``field_name``.

        Returns a contract dict.  Never returns the ORM record.
        """
        item = self._authorize_and_fetch_item(field_name)
        return {
            "contract_version": MEMO_DOCUMENT_CONTRACT_VERSION,
            "document_item_id": item.id,
            "storage_state": item.storage_state,
            "drive_id": item.sharepoint_drive_id,
            "item_id": item.sharepoint_item_id,
            "etag": item.sharepoint_etag,
            "file_size": item.file_size,
            "checksum": item.checksum,
            "connection_id": item.graph_connection_id.id,
            "document_uuid": item.uuid,
        }

    def get_document_download_url(self, field_name):
        """
        Return the internal download URL for the linked document.

        Returns only a safe URL string; no SharePoint credentials or raw IDs.
        """
        item = self._authorize_and_fetch_item(field_name)
        if item.storage_state != "available":
            raise UserError(
                _("The requested SharePoint document is not available.")
            )
        return f"/lhi/sharepoint/document/{item.uuid}/download"

    def create_pdf_document(self, pdf_content, filename, pdf_hash):
        """
        Create a new PDF document item under service elevation.

        Authorization is checked before any write.  The contract dict is
        returned after SharePoint upload confirmation.  Binary data is
        cleared from the spool after confirmation.
        """
        if not self._is_authorized_caller():
            raise AccessError(
                _("Only an authorized workflow participant may create Memo PDF documents.")
            )

        memo = self._memo

        # Validate content
        if not pdf_content or not pdf_content.startswith(b"%PDF"):
            raise UserError(
                _("The supplied content is not a valid PDF document.")
            )

        computed_hash = hashlib.sha256(pdf_content).hexdigest()
        if computed_hash != pdf_hash:
            raise UserError(
                _("The PDF content hash does not match the supplied hash.")
            )

        # Resolve policy under service elevation
        policy = (
            self._env["lhi.document.storage.policy"]
            .sudo()
            .resolve_policy("lhi.memo", "source_pdf_item_id", memo.company_id)
        )
        if not policy or policy.storage_backend != "sharepoint":
            raise UserError(
                _("No SharePoint storage policy is configured for Memo PDF documents.")
            )

        # Idempotency: check for existing confirmed PDF with same hash
        idempotency_key = self._env["lhi.document.item"].sudo()._make_idempotency_key(
            "lhi.memo",
            memo.id,
            "source_pdf_item_id",
            filename,
            computed_hash,
        )
        existing = (
            self._env["lhi.document.item"]
            .sudo()
            .search([("idempotency_key", "=", idempotency_key)], limit=1)
        )
        if existing:
            _logger.info(
                "Memo PDF creation: reusing existing item %s (idempotency key match) "
                "for memo %s",
                existing.id,
                memo.name,
            )
            return {
                "contract_version": MEMO_DOCUMENT_CONTRACT_VERSION,
                "document_item_id": existing.id,
                "storage_state": existing.storage_state,
                "content_hash": computed_hash,
                "file_size": existing.file_size,
                "version": existing.sharepoint_version or "",
            }

        # Create under narrow service elevation
        item = (
            self._env["lhi.document.item"]
            .sudo()
            .create_from_bytes(
                name=filename,
                content=pdf_content,
                mime_type="application/pdf",
                linked_model="lhi.memo",
                linked_record_id=memo.id,
                linked_field="source_pdf_item_id",
                requested_by=self._calling_user,
                synchronous=True,
            )
        )

        # Verify confirmation
        if item.storage_state != "available":
            raise UserError(
                _("SharePoint did not confirm the submitted memo PDF.")
            )
        if not item.sharepoint_item_id:
            raise UserError(
                _("SharePoint did not return a stable item ID for the memo PDF.")
            )

        # Verify file size and hash
        if item.file_size != len(pdf_content):
            raise UserError(
                _("Confirmed PDF file size does not match the generated content.")
            )
        if item.checksum and item.checksum != computed_hash:
            raise UserError(
                _("Confirmed PDF checksum does not match the generated content.")
            )

        # Clear spool data — binary must not remain in Odoo
        try:
            item._remove_spool()
        except Exception:
            _logger.warning(
                "Could not remove spool for confirmed PDF item %s (memo %s). "
                "Will be cleaned up by next reconciliation.",
                item.id,
                memo.name,
            )

        return {
            "contract_version": MEMO_DOCUMENT_CONTRACT_VERSION,
            "document_item_id": item.id,
            "storage_state": item.storage_state,
            "content_hash": computed_hash,
            "file_size": item.file_size,
            "version": item.sharepoint_version or "",
        }

    def update_docx_checksums(self, field_name, file_size, checksum, sha1):
        """Update the DOCX item checksums after PDF capture verification."""
        item = self._authorize_and_fetch_item(field_name)
        item.write(
            {
                "file_size": file_size,
                "checksum": checksum,
                "sha1_checksum": sha1,
            }
        )

    def apply_drive_item_metadata(self, field_name, graph_payload):
        """Update SharePoint metadata fields on the linked item."""
        item = self._authorize_and_fetch_item(field_name)
        item._apply_drive_item(graph_payload)

    def reconcile_document(self, field_name):
        """Trigger reconciliation on the linked document item."""
        item = self._authorize_and_fetch_item(field_name)
        item.action_reconcile()
        return True

    def get_sharepoint_web_url(self, field_name):
        """Return only the SharePoint web URL scalar (no live record)."""
        item = self._authorize_and_fetch_item(field_name)
        return item.sharepoint_web_url or ""
