# LHI Document Workspace

`lhi_document_workspace` provides permission-aware SharePoint document
workspaces inside Odoo 19 Community.

The module does not store business-document bytes. It renders the metadata and
immutable DriveItem references managed by `lhi_sharepoint_storage`, checks the
existing LHI business-record authorization before every action, and then uses
the signed-in user's delegated Microsoft identity for interactive Graph and
SharePoint operations.

Main capabilities:

- record- and project-scoped document lists;
- inline Microsoft preview as the default document action;
- Word, Excel, and PowerPoint editing in a new Microsoft 365 browser tab;
- Office desktop application links;
- delegated download, version history, governed existing links, replacement,
  new-version upload, and SharePoint recycle-bin archive;
- approved SharePoint Office templates;
- version, modified time, and modified-by metadata;
- focus-return metadata refresh and newer-version notifications;
- workflow-lock enforcement and audit events; and
- bounded, permission-filtered searches that never enumerate a whole library.

The module creates no new business role or authorization engine. Existing LHI
groups, ACLs, record rules, project assignments, approval controls, and
protected administrator roles remain authoritative.

See:

- `docs/administrator_guide.md`
- `docs/user_guide.md`
- `docs/deployment_and_rollback.md`
- `delivery_summary.md`
