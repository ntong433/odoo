# Deployment and rollback

## Configuration impact

Sprint 4 introduces no new environment variable and no new secret.

The existing variables from `lhi_microsoft_graph_core` and
`lhi_sharepoint_storage` remain required, including the Graph tenant/client and
client-secret environment configuration and `LHI_SHAREPOINT_SPOOL_DIR`. Do not place tenant
secrets, Graph tokens, SharePoint item IDs, production credentials, or webhook
secrets in source control.

The production base URL must be:

`https://work.lhinigeria.org`

## Entra and SharePoint prerequisites

- application Microsoft Graph `Sites.Selected`, explicitly assigned only to
  the approved LHI ERP SharePoint site with the required write role;
- delegated `Sites.Selected`, `openid`, `profile`, and `offline_access`, with
  users granted access to the approved SharePoint resources;
- no tenant-wide `Files.ReadWrite.All` or `Sites.ReadWrite.All`;
- versioning enabled on target libraries;
- recycle bin enabled;
- Office files configured to open in the browser where applicable;
- approved Word, Excel, and PowerPoint template DriveItems;
- no anonymous link requirement; and
- any explicit Odoo Content Security Policy must permit the Microsoft
  SharePoint/Office preview hosts used by the tenant in `frame-src`.

Validate the exact delegated selected-permission behavior in staging because
tenant conditional-access and SharePoint permission boundaries remain
deployment-specific.

## Deployment order

1. Back up PostgreSQL and the Odoo persistent data volume.
2. Export current Graph connection, library, policy, pending upload, and
   dead-letter diagnostics.
3. Confirm staging uses the same proxy, worker, WebSocket, and HTTPS behavior
   as production.
4. Deploy the image containing the Sprint 4 code.
5. Upgrade the compatibility dependencies and storage adapter:

   ```text
   odoo-bin -d <database> \
     -u lhi_fleet_operations,lhi_inventory,lhi_sharepoint_storage \
     --stop-after-init
   ```

6. Install or upgrade the workspace:

   ```text
   odoo-bin -d <database> \
     -u lhi_document_workspace \
     --stop-after-init
   ```

7. Restart/redeploy the Odoo service through Coolify.
8. Confirm `web.base.url` is `https://work.lhinigeria.org`.
9. Validate backend and unit-test asset bundle compilation.
10. Configure and validate approved Office templates in staging.
11. Execute the manual staging checklist below with non-administrator users.
12. Monitor Graph request logs, audit events, upload sessions, dead-letter
    jobs, browser console errors, Odoo workers, PostgreSQL, and Coolify health.

No production business file migration is part of this sprint.

## Manual staging checklist

Test each supported browser and representative record-rule boundary:

1. Word, Excel, PowerPoint, PDF, and image preview inside Odoo.
2. Microsoft 365 edit opens in a new tab and leaves Odoo open.
3. Two authorized users co-author one Office document.
4. Read-only and unauthorized users cannot edit or preview outside their
   permitted business scope.
5. Returning to Odoo refreshes ETag, version, modified time, and modified-by.
6. Popup-block behavior preserves the Odoo tab and creates no remote file.
7. Desktop Office links invoke the expected installed application.
8. Version history paginates and remains bounded.
9. Interrupted, throttled, and timed-out version chunks retry safely.
10. An ETag conflict or changed immutable item ID fails closed.
11. Template creation is model-scoped, idempotent, and immediately opens for
    edit.
12. Governed link requires normal Entra/SharePoint authentication.
13. Archive moves the item to the recycle bin and records an audit event.
14. A workflow-locked record allows read actions but denies mutations.
15. Project scope never shows documents from an unauthorized project.

Record screenshots or screen capture using non-production data and retain the
browser, user role, business record, expected result, actual result, and audit
event reference.

## Database changes

Normal Odoo installation creates `lhi_document_template` and its mail/activity
relations, adds two fields to `lhi_document_storage_policy`, and adds a
non-stored computed workspace field to the supported business models.

No custom SQL migration and no production data rewrite are required. The six
new storage policies are normal deterministic configuration records. Existing
document bytes and DriveItem identifiers are not moved.

## Rollback

Preferred rollback is configuration-first:

1. Disable **Workspace Enabled** on affected storage policies.
2. Remove user traffic during the rollback window.
3. Export template configuration and workspace audit references.
4. Revert the application image.
5. Upgrade the affected modules against the restored code only after verifying
   the database restore point.

Disabling workspace policies blocks workspace listing, preview, and version
confirmation without deleting SharePoint content.

If a full restore is required:

1. restore the pre-deployment PostgreSQL snapshot and Odoo volume;
2. reconcile SharePoint items or versions created after the snapshot using
   immutable item IDs and audit correlations;
3. retain or quarantine remote items according to Records Management
   direction; and
4. verify existing Sprint 3 attachment and OpenSign behavior before restoring
   user traffic.

Do not delete SharePoint documents during application rollback. Do not add a
permanent-local-storage fallback. Uninstalling the module is not the preferred
rollback because it drops template configuration and workspace fields while
remote documents remain authoritative.
