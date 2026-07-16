# Modification Sprint 5.1 delivery summary

## Outcome

Application-only Microsoft Graph authentication is standardized on the
environment-only OAuth 2.0 client-credentials flow:

- `ENTRA_TENANT_ID`
- `ENTRA_CLIENT_ID`
- `ENTRA_CLIENT_SECRET`
- scope `https://graph.microsoft.com/.default`
- grant type `client_credentials`

The existing token cache, expiry skew, retry, `Retry-After`, pagination,
structured request log, failure handling, reconciliation consumers, and
delegated-user authorization flow were retained. The repository did not already
use MSAL, so a second token implementation or a new dependency was not added.

No certificate file, private key, thumbprint, PFX password, or client assertion
is loaded or required. The Coolify/Traefik TLS certificate remains unrelated to
Microsoft Graph authentication.

Existing `lhi_security` groups, XML IDs, ACLs, record rules, project
assignments, approval matrices, segregation-of-duties rules, and protected local
administrator behavior were not changed.

Implementation is complete in the repository. Production acceptance remains
pending until an authorized operator supplies the real secret in Coolify,
confirms both redirect URIs in the Entra app registration, runs the live
validation script, redeploys, and records production smoke-test evidence.

## Changed files

Workspace and deployment:

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `Dockerfile.staging`
- `docker-compose.yml`
- `docker-compose.staging.yml`
- `scripts/validate_microsoft_env.sh`

Microsoft Graph foundation:

- `lhi_microsoft_graph_core/__manifest__.py`
- `lhi_microsoft_graph_core/models/graph_connection.py`
- `lhi_microsoft_graph_core/views/lhi_graph_connection_views.xml`
- `lhi_microsoft_graph_core/views/res_config_settings_views.xml`
- `lhi_microsoft_graph_core/tests/test_graph_core.py`
- `lhi_microsoft_graph_core/migrations/19.0.1.1.0/post-migrate.py`
- `lhi_microsoft_graph_core/README.md`
- `lhi_microsoft_graph_core/docs/administrator_guide.md`
- `lhi_microsoft_graph_core/docs/deployment_and_rollback.md`
- `lhi_microsoft_graph_core/docs/entra_sharepoint_configuration.md`
- `lhi_microsoft_graph_core/provisioning/Provision-LhiSharePoint.ps1`
- `lhi_microsoft_graph_core/provisioning/sharepoint_structure.json`
- `lhi_microsoft_graph_core/provisioning/README.md`
- this delivery summary

Dependent integration documentation and callback validation:

- `lhi_entra_identity_sync/models/entra_configuration.py`
- `lhi_entra_identity_sync/tests/test_entra_identity_sync.py`
- `lhi_entra_identity_sync/docs/administrator_guide.md`
- `lhi_entra_identity_sync/docs/deployment_and_rollback.md`
- `lhi_entra_identity_sync/docs/security_and_identity_architecture.md`
- `lhi_entra_identity_sync/delivery_summary.md`
- `lhi_document_workspace/docs/deployment_and_rollback.md`
- `lhi_document_workspace/delivery_summary.md`
- `lhi_sharepoint_storage/docs/deployment_and_rollback.md`

The local ignored `.env` content was not read or changed. Its filesystem mode
was hardened to `0600`.

## Authentication changes

Removed from the runtime implementation:

- certificate loading and validation;
- private-key loading;
- certificate thumbprint generation;
- JWT client assertions and `x5c`;
- certificate/client-secret reference resolution from Odoo records;
- production certificate startup checks;
- the `cryptography` external dependency.

Application token requests now post only:

```text
client_id=<ENTRA_CLIENT_ID>
client_secret=<ENTRA_CLIENT_SECRET>
scope=https://graph.microsoft.com/.default
grant_type=client_credentials
```

The secret is read immediately from the protected process environment. It is not
stored in an Odoo configuration field, returned by a controller, included in an
authorization URL, or sent to browser JavaScript.

Application tokens are used by the existing app-only consumers, including
Odoo-generated uploads, folder provisioning, synchronization, migration,
reconciliation, change processing, and Entra identity synchronization.

Delegated document operations remain user-context operations. The confidential
web application uses its client secret only to authenticate the server-side
authorization-code or refresh-token exchange; the resulting token represents the
signed-in user and does not permit application impersonation.

## Models and fields

No new model was created.

Removed from `lhi.graph.connection`:

- `application_credential_type`
- `certificate_identifier`
- `certificate_reference`
- `private_key_reference`
- `private_key_password_reference`
- `client_secret_reference`

The existing protected `lhi.graph.token` cache and request/diagnostic models are
unchanged.

## Database migration

Module version: `19.0.1.1.0`.

The post-migration:

1. drops all six obsolete credential-reference columns from
   `lhi_graph_connection`;
2. copies only non-secret confirmed environment identifiers into reference
   fields;
3. sets the configured drive candidate for existing logical library records;
4. deletes cached application tokens so the first post-upgrade request uses
   `ENTRA_CLIENT_SECRET`.

No business document, attachment, RBAC, approval, signature, project, or
production business record is migrated.

Upgrade verification used a synthetic old schema containing all six legacy
columns. The `19.0.1.1.0` migration ran successfully and all six columns and
field metadata records were absent afterward.

## Final environment-variable contract

Required before Odoo container startup:

- `ENTRA_TENANT_ID`
- `ENTRA_CLIENT_ID`
- `ENTRA_CLIENT_SECRET`
- `SHAREPOINT_SITE_ID`
- `SHAREPOINT_DRIVE_ID`
- `SHAREPOINT_ROOT_ITEM_ID`

Confirmed non-secret production values:

- `LHI_PUBLIC_URL=https://work.lhinigeria.org`
- `ENTRA_TENANT_ID=552a1d00-ce70-4fdb-940f-0ad131e4b9cb`
- `ENTRA_CLIENT_ID=02b3748f-e84b-4bec-935a-21fab1498517`
- `SHAREPOINT_HOSTNAME=lhisokoto.sharepoint.com`
- `SHAREPOINT_SITE_PATH=/sites/ERP`
- `SHAREPOINT_SITE_ID=lhisokoto.sharepoint.com,a307baa8-0966-493a-8c93-147ab14d086d,88f486b7-3c86-436f-a0de-0968fbf2d420`
- `SHAREPOINT_LIBRARY_NAME=Documents`
- `SHAREPOINT_DRIVE_ID=b!qLoHo2YJOkmMkxR6sU0IbbeG9IiGPG9DoN4JaPvy1CAv6wvCWH9ZQIOHqh5ZXKtf`
- `SHAREPOINT_ROOT_FOLDER=ERP`
- `SHAREPOINT_ROOT_ITEM_ID=01QTWNMA2W4O2DS5DA5VBIK7ARAKQREBQT`

Protected values set only in Coolify:

- `ENTRA_CLIENT_SECRET`
- `GRAPH_WEBHOOK_CLIENT_STATE`
- PostgreSQL and Odoo administrative passwords

Forbidden certificate variables are rejected by startup validation:

- `ENTRA_CERTIFICATE_PATH`
- `ENTRA_CERTIFICATE_THUMBPRINT`
- `ENTRA_PRIVATE_KEY`
- `ENTRA_PFX_PATH`
- `ENTRA_PFX_PASSWORD`
- legacy `LHI_GRAPH_CERTIFICATE_PEM`
- legacy `LHI_GRAPH_PRIVATE_KEY_PEM`
- legacy `LHI_GRAPH_PRIVATE_KEY_PASSWORD`

The complete optional feature, timeout, retry, maintenance-login, document, and
synchronization settings are documented in the generated `.env.example`.

## Redirect URIs discovered in code

Primary Odoo Entra SSO callback:

`https://work.lhinigeria.org/auth_oauth/signin`

Delegated Microsoft Graph authorization-code/PKCE callback:

`https://work.lhinigeria.org/lhi/microsoft_graph/oauth/callback`

The primary callback comes from Odoo `auth_oauth`. The delegated callback is
implemented by
`lhi_microsoft_graph_core/controllers/delegated_oauth.py`.

`lhi_entra_identity_sync` now rejects OAuth-provider configuration when
`ENTRA_REDIRECT_URI` differs from the primary callback.

The repository proves the exact callback values used by the application. The
actual Entra portal registration was not accessible from this workspace and
must be confirmed by an authorized Entra administrator before deployment.

## Required Entra and SharePoint permissions

Application permissions:

- Microsoft Graph `Sites.Selected`
- Microsoft Graph `User.Read.All` for approved identity/manager synchronization
- Microsoft Graph `GroupMember.Read.All` for approved transitive mapped-group
  synchronization

Delegated permissions:

- `openid`
- `profile`
- `email`
- `offline_access`
- Microsoft Graph `User.Read`
- Microsoft Graph delegated `Sites.Selected`

SharePoint must retain the explicit `write` selected-site assignment for client
ID `02b3748f-e84b-4bec-935a-21fab1498517` on the ERP site. Tenant-wide
application file/site permissions are not required.

## SharePoint configuration

The provisioned structure is standardized on:

```text
Documents/
└── ERP/
    ├── Projects/
    ├── Procurement/
    ├── Operations/
    ├── Controlled Documents/
    └── Signed Documents/
```

The logical Odoo storage roles map below the validated immutable ERP root
DriveItem. Project templates retain the nine governed project subfolders.

## Secret-safe diagnostics

Diagnostics disclose only configuration booleans, outcome, token expiry,
Microsoft request ID, and SharePoint site/drive/root status.

Redaction covers:

- environment client-secret and webhook-state values, including unlabelled
  appearances;
- JSON, form, and text `client_secret` values;
- access, refresh, and ID tokens;
- authorization bearer headers;
- webhook client-state values.

No token response body is written to structured logs.

## Automated test results

Executed on 2026-07-16 with synthetic secrets and mocked Microsoft responses.

`lhi_microsoft_graph_core`:

```text
23 Odoo tests
21 test methods
0 failed
0 errors
0.97 seconds
608 test queries
```

Coverage includes missing, invalid, and expired secret responses; successful
client credentials; cache reuse; renewal before expiry; throttling and
`Retry-After`; pagination; secret redaction; site, drive, and root DriveItem
validation; token ACL denial; local-login fail-safe; delegated code/PKCE; and
certificate environment variables not being used by token authentication.

Previously executed dependent regression suites after the Sprint 5.1 changes:

| Module | Result |
|---|---|
| `lhi_entra_identity_sync` | 14 Odoo tests, 12 methods, 0 failures/errors |
| `lhi_sharepoint_storage` | 10 Odoo tests, 8 methods, 0 failures/errors |
| `lhi_document_workspace` | 13 Odoo tests, 11 methods, 0 failures/errors |
| `lhi_signature_bridge` | 3 Odoo tests, 1 method, 0 failures/errors |

Additional verification:

- fresh database install and startup without certificate variables/files:
  passed;
- synthetic old-schema module upgrade: passed;
- Python compile: passed;
- XML syntax parse: passed for 20 affected XML files;
- shell syntax validation: passed;
- development Compose resolution: passed;
- staging Compose resolution: passed;
- validator success path: exit `0`;
- validator missing-secret path: exit `1`;
- validator forbidden-certificate-variable path: exit `1`.

## Cross-module regression findings

A combined legacy workflow run was attempted. Project workplan, fleet, and
signature tests reached successful completion, but the full suite could not
complete because of unrelated existing Odoo 19 compatibility defects:

1. `lhi_purchase_request` calls `lhi.procurement.commitment` while that model is
   unavailable at its test/load point.
2. `lhi_inventory` test setup uses obsolete product type value `product`.
3. `lhi_accounting_base` security XML writes removed Odoo 19
   `res.groups.category_id`.

These modules were not changed in this authentication sprint. The failures are
recorded as pre-existing regression blockers and must be corrected before a
full green production regression claim can be made.

## Manual and production test evidence

Completed locally:

- Odoo installed and loaded the Graph module without a certificate mount;
- startup validation reported only yes/no configuration status;
- no protected value appeared in validator or Odoo test output;
- exact callbacks were traced to their controller/provider implementations;
- the existing local administrator login fail-safe test remained green;
- logical SharePoint libraries were configured against the confirmed drive and
  immutable ERP root identifier.

Not executed from this workspace:

- live token acquisition with the real production client secret;
- live SharePoint site, drive, and ERP root access;
- Entra portal redirect-URI inspection;
- Coolify production redeployment;
- browser SSO, preview, Microsoft 365 editing, and co-authoring smoke tests;
- live Entra manager/group synchronization;
- live project, procurement, inventory, fleet, and OpenSign regression.

## Coolify deployment instructions

1. Back up PostgreSQL and the Odoo persistent volume.
2. In the Entra app registration, confirm both exact production redirect URIs.
3. Confirm required Graph permissions have administrator consent.
4. Confirm the ERP SharePoint site retains the explicit `Sites.Selected`
   `write` assignment.
5. In Coolify protected environment settings, set the complete contract from
   `.env.example`, especially `ENTRA_CLIENT_SECRET` and
   `GRAPH_WEBHOOK_CLIENT_STATE`.
6. Remove every deprecated certificate variable and certificate/key mount.
7. Redeploy the staging service.
8. Run `/opt/odoo/scripts/validate_microsoft_env.sh --full` inside the staging
   Odoo container.
9. Upgrade `lhi_microsoft_graph_core`, then upgrade
   `lhi_entra_identity_sync`, `lhi_sharepoint_storage`, and
   `lhi_document_workspace`.
10. Run Graph diagnostics and the documented browser/background smoke tests.
11. Repeat the controlled deployment in production.

Do not paste the client secret into deployment logs, shell history, tickets, or
Odoo settings.

## Client-secret rotation

1. Create a second Entra client secret before the current secret expires.
2. Copy the secret value immediately; do not use the Secret ID.
3. Replace `ENTRA_CLIENT_SECRET` in Coolify protected settings.
4. Redeploy Odoo.
5. Clear the application token cache from Graph administration or restart the
   container.
6. Run the full validator and Graph diagnostics.
7. Verify background upload, reconciliation, and Entra synchronization.
8. Delete the old secret only after the new secret is proven.
9. Record the rotation in the protected operations log and schedule the next
   rotation before expiry.

No database secret update is required.

## Rollback procedure

1. Stop document migration and local purge jobs.
2. Preserve failed/pending queues and do not enable local storage fallback.
3. Restore the pre-deployment database and Odoo persistent-volume backups.
4. Redeploy the previous application image/commit and its matching environment
   contract.
5. Restore the prior Entra credential method only as an explicit emergency
   rollback; never combine certificate and client-secret modes.
6. Validate protected local administrator access.
7. Reconcile SharePoint items created after the backup before retrying business
   workflows.

Rotating back to the previous client secret is possible only while that secret
is still valid. Do not remove the new secret until rollback verification is
complete.

## Remaining risks

- Production Graph/SharePoint access and Coolify redeployment require the real
  protected secret and authorized tenant access.
- The Entra app registration redirect URIs have not been independently observed
  from this workspace.
- Client secrets are shared credentials and require disciplined rotation,
  restricted Coolify access, and incident response.
- The three pre-existing cross-module Odoo 19 defects block a complete green
  legacy workflow suite.
- `GRAPH_WEBHOOK_URL` is present in the environment contract, but the configured
  notification route must be verified against the deployed webhook module
  before enabling subscriptions.
- The workspace root is not currently a Git worktree; ensure the root
  deployment files and `custom-addons` changes are added to the actual protected
  deployment repository before release.
