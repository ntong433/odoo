# LHI SharePoint Document Storage

`lhi_sharepoint_storage` is the policy-based business-document storage adapter
for LHI ERP on Odoo 19 Community.

It keeps Odoo's normal attachment storage for technical content and routes only
explicitly configured business records to SharePoint Online. Odoo retains
metadata, business links, workflow state, permissions mapping, audit references,
and bounded temporary processing data. A document is never marked available
until SharePoint returns and Odoo verifies the immutable DriveItem identifier.

## Main components

- `lhi.document.item`: durable Odoo metadata and SharePoint DriveItem reference.
- `lhi.document.storage.policy`: explicit model-specific routing policy.
- `ir.attachment` adapter: compatibility for chatter, attachment-backed Binary
  fields, downloads, e-mail processing, and existing business views.
- Delegated direct-upload controller and Owl field widget.
- Small-file and resumable upload services.
- Existing `lhi.integration.job` retry/dead-letter extension.
- Reconciliation, upload-session expiry, and orphan-spool cleanup crons.

See:

- `docs/administrator_guide.md`
- `docs/security_and_storage_architecture.md`
- `docs/deployment_and_rollback.md`
- `delivery_summary.md`

