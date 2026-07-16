# Administrator guide

## Prerequisites

1. Install and configure `lhi_microsoft_graph_core`.
2. Validate the LHI ERP SharePoint site and all five library roles:
   Projects, Procurement, Operations, Controlled Documents, and Signed
   Documents.
3. Provision the Sprint 2 SharePoint columns and project folder template.
4. Assign the Entra application `Sites.Selected` access with the approved
   `write` role only on the LHI ERP SharePoint site.
5. Configure delegated `Sites.Selected` authorization for users who upload,
   download, preview, or edit documents.
6. Configure a persistent, encrypted Coolify volume path in
   `LHI_SHAREPOINT_SPOOL_DIR`.

## Menus

ERP administrators use:

- Integration → Configuration → Microsoft Graph → Document Storage Policies
- Integration → Monitoring → SharePoint Documents
- Integration → Monitoring → Integration Jobs
- Integration → Monitoring → Graph Request Logs

Internal auditors have read-only access to document metadata and Graph request
logs. Ordinary users receive no direct ACL to `lhi.document.item`; they work
through authorized business records and attachment controllers.

## Policy administration

Before activating a new policy:

1. Confirm the model is a business-document owner, not a technical model.
2. Test create, read, update, download, e-mail, copy, delete, chatter preview,
   report generation, and record deletion in staging.
3. Select the narrowest library and folder strategy.
4. Set extensions and maximum size explicitly.
5. Keep upload chunks below 60 MiB and in multiples of 320 KiB.
6. Select `fail` conflict behavior unless version replacement is an approved
   workflow.
7. Confirm all required metadata columns and retention values exist.
8. Test with a non-administrator identity subject to real record rules.

## Failure operations

- `failed`: upload or metadata confirmation failed; bytes are in the protected
  spool if a server retry is possible.
- `dead_letter`: retry limit was reached; inspect the safe error and Graph logs,
  correct the cause, then use **Retry Upload**.
- `missing`: reconciliation cannot find the DriveItem.
- `mismatch`: size, hash, identity, or metadata no longer matches.

Never copy a failed spool file into the Odoo filestore. Correct Graph,
SharePoint, permission, metadata, or network configuration and retry.

## Generated documents

Other modules should use:

```python
self.env["lhi.document.item"].create_from_bytes(
    name="document.pdf",
    content=pdf_bytes,
    mime_type="application/pdf",
    linked_model=record._name,
    linked_record_id=record.id,
    linked_field=False,
    requested_by=self.env.user,
    synchronous=True,
)
```

The LHI Signature Bridge uses this path for generated purchase-order PDFs,
signed PDFs, and audit certificates. OpenSign dispatch and completion are
blocked when SharePoint confirmation is incomplete.

## Reconciliation

The scheduled reconciliation checks bounded batches of available and degraded
documents. It re-reads each DriveItem by drive and item ID, checks item identity,
size, and available hashes, and records the outcome. It does not depend on a
mutable path.

Upload-session expiry runs every 15 minutes. Server-spooled uploads receive a
new resumable session; browser-only sessions become visibly failed and can be
restarted by the user. Orphan processing files older than 24 hours and not
referenced by Odoo are removed daily.

