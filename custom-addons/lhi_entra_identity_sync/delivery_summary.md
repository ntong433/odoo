# Modification Sprint 5 delivery summary

## Outcome

`lhi_entra_identity_sync` implements Entra identity, manager, account-state, and
approved existing-group synchronization without creating a second RBAC system.
Existing Odoo group XML IDs, ACLs, record rules, project assignments, approval
matrices, segregation-of-duties rules, and protected administrator roles remain
authoritative.

The implementation includes bounded Graph discovery, nested group checks,
idempotent dry-run planning, configuration-drift protection, transactional
per-user application, failure retry, reconciliation diagnostics, immutable
before/after snapshots, drift-safe rollback, protected maintenance login, and
manager-aware approval routing that preserves submitted approver snapshots.

## Changed files

New module:

- `custom-addons/lhi_entra_identity_sync/README.md`
- `custom-addons/lhi_entra_identity_sync/__init__.py`
- `custom-addons/lhi_entra_identity_sync/__manifest__.py`
- `custom-addons/lhi_entra_identity_sync/controllers/__init__.py`
- `custom-addons/lhi_entra_identity_sync/controllers/main.py`
- `custom-addons/lhi_entra_identity_sync/data/ir_cron.xml`
- `custom-addons/lhi_entra_identity_sync/delivery_summary.md`
- `custom-addons/lhi_entra_identity_sync/docs/administrator_guide.md`
- `custom-addons/lhi_entra_identity_sync/docs/deployment_and_rollback.md`
- `custom-addons/lhi_entra_identity_sync/docs/security_and_identity_architecture.md`
- `custom-addons/lhi_entra_identity_sync/models/__init__.py`
- `custom-addons/lhi_entra_identity_sync/models/approval_matrix.py`
- `custom-addons/lhi_entra_identity_sync/models/audit_log.py`
- `custom-addons/lhi_entra_identity_sync/models/entra_configuration.py`
- `custom-addons/lhi_entra_identity_sync/models/entra_group_mapping.py`
- `custom-addons/lhi_entra_identity_sync/models/entra_sync_run.py`
- `custom-addons/lhi_entra_identity_sync/models/hr_employee.py`
- `custom-addons/lhi_entra_identity_sync/models/res_groups.py`
- `custom-addons/lhi_entra_identity_sync/models/res_users.py`
- `custom-addons/lhi_entra_identity_sync/security/ir.model.access.csv`
- `custom-addons/lhi_entra_identity_sync/security/lhi_entra_identity_security.xml`
- `custom-addons/lhi_entra_identity_sync/tests/__init__.py`
- `custom-addons/lhi_entra_identity_sync/tests/test_entra_identity_sync.py`
- `custom-addons/lhi_entra_identity_sync/views/approval_matrix_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/entra_configuration_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/entra_group_mapping_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/entra_sync_run_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/hr_employee_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/lhi_entra_identity_menus.xml`
- `custom-addons/lhi_entra_identity_sync/views/res_groups_views.xml`
- `custom-addons/lhi_entra_identity_sync/views/res_users_views.xml`

Compatibility changes:

- `.env.example`
- `docker-compose.yml`
- `docker-compose.staging.yml`
- `custom-addons/lhi_integration/models/res_users.py`
- `custom-addons/lhi_integration/models/hr_employee.py`
- `custom-addons/lhi_approval_matrix/models/lhi_approval_matrix.py`
- `custom-addons/lhi_approval_matrix/models/lhi_approval_request.py`

No Odoo core file was changed.

## New models

- `lhi.entra.configuration`: company-scoped connection, SSO, sync scope,
  deactivation, operational bounds, activation, and status configuration.
- `lhi.entra.group.mapping`: approved Entra group object ID to an existing
  `res.groups` record, with management mode, priority, conflict policy, and state.
- `lhi.entra.sync.run`: idempotency, execution state, counters, retry queue,
  hashes, configuration fingerprint, and rollback metadata.
- `lhi.entra.sync.plan`: matched user, proposed changes, state, and local-state
  hash.
- `lhi.entra.sync.finding`: would-add, would-remove, preserve, block,
  segregation-conflict, missing-mapping, and missing-manager diagnostics.
- `lhi.entra.sync.snapshot`: immutable before/after state and hashes for rollback.

## New and extended fields

`res.users`:

- `entra_object_id`, `entra_tenant_id`, `entra_upn`,
  `entra_account_enabled`, `entra_manager_object_id`,
  `entra_manager_user_id`, `entra_last_sync_at`, `entra_sync_state`,
  `identity_source`, `entra_given_name`, `entra_family_name`,
  `entra_login_blocked`, and `lhi_local_maintenance_admin`.

`hr.employee`:

- Related Entra identity/status fields plus synchronized `parent_id` reporting
  line updates. Existing HR, department, office, and user relationships are
  reused.

`res.groups`:

- `lhi_entra_management_mode` and `lhi_entra_mapping_count`; no functional group
  is created.

Approval and audit extensions:

- `lhi.approval.matrix.line.approver_source`
- `lhi.approval.request.manager_reassignment_count`
- explicit manager-reassignment history action
- additional Entra synchronization audit-event selections

## Environment variables

- `LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS`: required allow-list for the protected
  local maintenance login.
- `LHI_ENTRA_TRUST_PROXY_HEADERS`: defaults to `false`; enable only when the
  trusted Coolify proxy sanitizes and overwrites `X-Forwarded-For`.

The Graph core client-secret token service is reused. No tenant secret, token,
password, production credential, or webhook secret is stored in Odoo or source
control.

## Required Entra configuration and permissions

Delegated sign-in:

- Redirect URI: `https://work.lhinigeria.org/auth_oauth/signin`
- Scopes: `openid`, `profile`, `email`, `User.Read`

Application synchronization:

- `User.Read.All`
- `GroupMember.Read.All`
- administrator consent

Only approved mapped group object IDs are evaluated. Routine synchronization
defaults to existing Entra-linked Odoo users. An approved Entra scope group can
be used for controlled discovery; whole-directory mode is bounded and intended
for diagnostics.

The existing Odoo 19 OAuth provider uses an implicit access-token response.
Microsoft recommends authorization-code flow for new applications; replacement
of the authentication adapter is a documented follow-up risk.

## Required SharePoint configuration

No SharePoint library, column, content type, folder, or retention change is
introduced by Sprint 5. Preserve the existing `Sites.Selected` application
permission and explicit assignment to the approved LHI ERP SharePoint site.

## Database migration

Odoo creates the new tables, constraints, indexes, and extended-model columns
during module installation or upgrade. The post-install hook copies existing
`lhi_entra_object_id` values into canonical `entra_object_id` only when the new
field is empty.

No existing group XML ID, ACL, record rule, project assignment, approval request,
or approver snapshot is migrated or replaced. No production data was modified
during this sprint.

## Automated test results

Executed on the isolated PostgreSQL database `lhi_entra_sprint5_test`:

```text
Odoo 19 install/upgrade and Sprint 5 tests
Command: docker compose run --rm --no-deps odoo python3
         /opt/odoo/odoo/odoo-bin -c /etc/odoo/odoo.conf
         -d lhi_entra_sprint5_test -u lhi_entra_identity_sync
         --test-enable --test-tags /lhi_entra_identity_sync
         --stop-after-init --log-level=test --logfile=/dev/stdout
Result: 11 test methods, 13 assertions/tests reported by Odoo,
        0 failed, 0 errors, 1.74 seconds, 1,320 queries.
```

Covered: mapped-group add, Odoo-managed preservation, apply, rollback, disabled
identity fail-closed behavior, protected administrator preservation, protected
group rejection, SoD conflict blocking, manager approver snapshot preservation,
ordinary-user configuration ACL denial, idempotency-key reuse, failure queue
creation without role changes, and post-plan configuration-drift rejection.

```text
Existing approval-matrix regression
Command: install lhi_feature_control and upgrade/test lhi_approval_matrix
         with --test-tags /lhi_approval_matrix
Result: 7 test methods, 9 assertions/tests reported by Odoo,
        0 failed, 0 errors, 1.59 seconds, 1,047 queries.
```

Static verification:

- Python AST validation: 19 affected Python files passed.
- XML parsing: 10 module XML files passed.
- Docker Compose validation: development and staging configurations passed.
- Odoo module installation and subsequent upgrade both completed successfully.

## Manual test evidence

- Local development Odoo service restored after test execution.
- `GET http://127.0.0.1:8069/web/health` returned HTTP 200 with
  `{"status": "pass"}`.
- Database and Odoo containers were running after restoration.
- Views, security data, cron records, menus, constraints, and database tables
  loaded during installation/upgrade.

Not executed: live Entra authentication, live Graph synchronization, production
Coolify routing, Cloudflare/VPN maintenance-route enforcement, or staging tenant
consent. These require approved external configuration and identities.

## Deployment instructions

1. Back up PostgreSQL and the Odoo persistent data volume.
2. Deploy the changed addons, Compose definitions, and protected Coolify
   environment variables.
3. Upgrade `lhi_integration` and `lhi_approval_matrix`; install or upgrade
   `lhi_entra_identity_sync`.
4. Keep primary SSO, write mode, and both scheduled actions disabled.
5. Confirm production `web.base.url` is exactly
   `https://work.lhinigeria.org`.
6. Configure the tenant-scoped OAuth provider and approved existing-group
   mappings.
7. Designate and test two protected local maintenance administrators.
8. Run and resolve a staging dry run. Approve the exact run and enable write mode
   within 24 hours; configuration or SoD drift requires a fresh run.
9. Validate manager, department, office, group, deactivation, login, audit, and
   rollback outcomes in staging.
10. Enable primary SSO and scheduled reconciliation only in the approved
    production change window.

## Rollback procedure

For a synchronization run, use its rollback action. Rollback refuses to overwrite
a user whose current state no longer matches the recorded post-sync hash.

For deployment rollback:

1. Disable primary SSO, write synchronization, and scheduled actions.
2. Roll back affected applied runs where appropriate.
3. Verify protected local maintenance access.
4. Restore the prior image/custom-addons revision.
5. Upgrade modules if required by that revision.
6. Restore the pre-deployment database backup only for an approved schema/data
   rollback.

Do not routinely uninstall the module because that removes diagnostic and
snapshot evidence.

## Remaining risks

- Live Entra login, Graph permissions, nested membership, throttling, and
  deactivation must still be proven in staging with the approved tenant.
- Odoo's current implicit OAuth flow should be replaced with an
  authorization-code/PKCE adapter in a later approved security sprint.
- Department and office synchronization depends on unique, governed,
  case-insensitive names in existing LHI master data.
- Application directory permissions cannot be constrained with SharePoint-style
  `Sites.Selected`; processing is therefore restricted in Odoo to approved user
  and group scope.
- Coolify proxy trust and maintenance CIDRs must be configured correctly before
  activation. Keep proxy-header trust disabled otherwise.
- Production worker, WebSocket, backup, monitoring, and recovery settings require
  final Coolify staging evidence; this sprint validates the repository Compose
  definitions only.
