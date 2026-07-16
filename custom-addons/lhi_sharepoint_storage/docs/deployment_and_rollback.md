# Deployment and rollback

## New environment variable

`LHI_SHAREPOINT_SPOOL_DIR`

Recommended Coolify value:

`/var/lib/odoo/lhi-sharepoint-spool`

Mount this path on persistent encrypted storage. The Odoo process user requires
exclusive read/write access. The module enforces directory mode `0700` and file
mode `0600`. Do not expose the path through Nginx or a Coolify public file mount.

The client-secret and SharePoint identifier contract from
`lhi_microsoft_graph_core` remains required. The client secret is supplied only
through protected Coolify environment settings. No tenant secret, password,
token, SharePoint item ID, database credential, or webhook secret is stored in
source control.

## Deployment order

1. Back up the PostgreSQL database and Odoo data volume.
2. Export the current Graph connection/library configuration and integration
   queue status.
3. Confirm `https://work.lhinigeria.org` is the production `web.base.url`.
4. Create and secure `LHI_SHAREPOINT_SPOOL_DIR`.
5. Deploy and validate the code in staging before production user traffic.
6. Upgrade `lhi_microsoft_graph_core`.
7. Install/upgrade `lhi_sharepoint_storage`.
8. Upgrade the existing attachment-producing LHI modules changed by this
   sprint. Odoo dependency ordering installs the storage foundation first.
9. Validate all SharePoint libraries and delegated authorization in staging.
10. Run installation, Python, asset, access-control, upload interruption,
    reconciliation, generated-PDF, OpenSign callback, and upgrade tests.
11. The shipped business policies are active after installation. For a phased
    rollout, deactivate selected policies during the maintenance window before
    restoring user traffic, then enable them in controlled groups beginning
    with a low-risk project document workflow.
12. Monitor Graph request logs, failed documents, dead-letter jobs, spool
    capacity, PostgreSQL, workers, and Coolify health checks.

Do not enable document migration in this sprint. Existing local business bytes
remain for the later `lhi_document_migration` controlled migration.

## Database changes

Normal Odoo module upgrade creates:

- `lhi_document_item`
- `lhi_document_storage_policy`
- mail/chatter relation tables for document metadata
- SharePoint fields on `ir_attachment`
- idempotency, operation, and company fields on `lhi_integration_job`
- SharePoint document-reference fields on `lhi_opensign_request`

The existing OpenSign Binary fields remain attachment-compatible for historical
records. New processing bytes are cleared after they have been transferred to
the protected spool and associated with SharePoint metadata. No SQL migration
script or production data rewrite is performed.

## Rollback

Preferred rollback is configuration-first:

1. Deactivate affected document storage policies.
2. Stop the three SharePoint storage crons.
3. Prevent new uploads while preserving read access.
4. Export all `lhi.document.item` metadata and pending/dead-letter jobs.
5. Revert the application image and upgrade the affected modules only after a
   database restore plan is approved.

Do not uninstall `lhi_sharepoint_storage` while remote attachments reference
its metadata. Do not delete SharePoint files during application rollback.

For a full database restore:

1. Restore the pre-deployment PostgreSQL and Odoo-volume snapshots.
2. Reconcile SharePoint items created after the snapshot using their LHI audit
   correlation IDs.
3. Retain or quarantine those remote items according to Records Management
   direction.
4. Restore standard attachment widgets only after confirming no active record
   depends on byte-free compatibility attachments.

There is intentionally no automatic permanent-local-storage fallback. A
rollback that needs local business bytes must be a controlled reverse migration,
not an availability shortcut.
