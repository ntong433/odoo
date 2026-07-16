# Coolify deployment, secret rotation, and rollback

## Required protected environment contract

Required for container startup:

| Variable | Secret | Production value |
|---|---:|---|
| `ENTRA_TENANT_ID` | No | `552a1d00-ce70-4fdb-940f-0ad131e4b9cb` |
| `ENTRA_CLIENT_ID` | No | `02b3748f-e84b-4bec-935a-21fab1498517` |
| `ENTRA_CLIENT_SECRET` | Yes | Set the secret value in protected Coolify settings |
| `SHAREPOINT_SITE_ID` | No | Confirmed ERP site ID |
| `SHAREPOINT_DRIVE_ID` | No | Confirmed `Documents` drive ID |
| `SHAREPOINT_ROOT_ITEM_ID` | No | Confirmed immutable `ERP` DriveItem ID |

Also configure the non-secret hostname, site path, library name, root folder,
redirect URIs, Graph endpoint, and operational limits from `.env.example`.

Do not configure Microsoft application certificate paths, fingerprints, keys,
PFX files, or key passwords. The Coolify/Traefik HTTPS certificate is unrelated
to Microsoft Graph authentication.

## Pre-deployment

1. Back up PostgreSQL and the Odoo persistent data volume.
2. Confirm the Entra app has both exact production redirect URIs.
3. Confirm `Sites.Selected` administrator consent and explicit `write`
   assignment to the ERP site for client ID
   `02b3748f-e84b-4bec-935a-21fab1498517`.
4. Add `ENTRA_CLIENT_SECRET` as a protected Coolify runtime variable. Never add
   it as a build argument or Dockerfile value.
5. Remove all deprecated Microsoft application certificate variables from the
   Coolify service.
6. Run `scripts/validate_microsoft_env.sh` in staging.
7. Confirm `web.base.url` is `https://work.lhinigeria.org`.

## Deployment

1. Deploy the changed image and Compose configuration.
2. Run the Odoo upgrade with ordinary HTTP workers stopped:

   ```bash
   python3 /opt/odoo/odoo-bin server \
     -c /etc/odoo/odoo.conf \
     -d PRODUCTION_DATABASE \
     -u lhi_microsoft_graph_core,lhi_sharepoint_storage,lhi_document_workspace,lhi_entra_identity_sync \
     --stop-after-init --no-http --workers=0
   ```

3. Restart the Coolify service.
4. Verify `/web/health`.
5. Run Graph diagnostics and confirm token, site, drive, and ERP root success.
6. Verify primary Entra sign-in, delegated Microsoft authorization, preview,
   edit-in-new-tab, background upload, and identity synchronization.
7. Confirm no secret or token is present in Odoo or Coolify logs.

The module migration clears cached application tokens so the first
post-upgrade app-only operation uses `ENTRA_CLIENT_SECRET`.

## Client-secret rotation

1. Create a second Entra client secret before the current secret expires.
2. Copy the new secret **value**, not its Secret ID, directly into the protected
   `ENTRA_CLIENT_SECRET` Coolify setting.
3. Redeploy or restart the Odoo service so workers receive the new environment.
4. As an ERP administrator, select **Clear App Token Cache** on the Graph
   connection.
5. Run `scripts/validate_microsoft_env.sh` and Odoo Graph diagnostics.
6. Verify one app-only upload/reconciliation operation and one Entra sync.
7. Remove the old secret from Entra only after successful verification.
8. Record the new expiry date and next rotation window without recording the
   secret value.

## Rollback

1. Disable document migration, Graph background sync, and Entra write sync.
2. Keep primary SSO and protected maintenance access under explicit review.
3. Restore the previous protected client secret in Coolify if the rotation
   itself caused the incident.
4. Clear the application token cache and rerun validation.
5. If code rollback is required, restore the previous image and matching
   database backup.
6. Preserve Graph diagnostics, request IDs, sync snapshots, and failure queues.

Do not uninstall the module as the first rollback action. Do not delete remote
SharePoint files during application rollback.
