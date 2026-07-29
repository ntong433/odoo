# LHI Asset Register and HUB Management — Delivery Summary

## Release status

The requested Odoo 19 Community implementation is complete in source control
as a release candidate. It is not yet approved for production because this
workspace has no PostgreSQL service and cannot access the Docker socket.
Database installation/upgrade, migration, multi-worker concurrency, browser,
LHI Sign, SharePoint, and Coolify checks therefore remain mandatory staging
gates.

No Odoo core file was modified. No production system, tenant, database,
SharePoint library, LHI Sign provider, or Coolify deployment was changed.

## Delivery phases and commits

1. `96bc59955b2` — `[DOC] audit Asset Register and HUB architecture`
2. `c9c91974fdb` — `[FIX] decouple operational platform from HR and Accounting`
3. `1f287621275` — `[ADD] deliver operational Asset Register`
4. `ff42bcd1e6d` — `[ADD] deliver governed HUB management`

The architecture audit is
`docs/lhi_asset_hub_dependency_architecture_audit.md`. Exhaustive module-level
file, model, field, configuration, migration, and risk details are in:

- `custom-addons/lhi_asset_management/delivery_summary.md`
- `custom-addons/lhi_hub_management/docs/DELIVERY_SUMMARY.md`

## Delivered scope

### Operational foundation

- HR- and Accounting-free operational dependency closure.
- `res.users`-based identity and organizational access, compatible with the
  existing Entra synchronization.
- Existing Odoo RBAC remains authoritative; Entra is not used as a second
  authorization engine.
- Stable Programmatic Operations and Operations navigation.

### Asset Register

- Existing `lhi.asset` extended rather than duplicated.
- Configurable atomic asset tags, legacy-tag preservation, controlled re-tag,
  configurable conditions, immutable lifecycle history, operational values,
  custody/location/HUB/project/funding/ownership data, SharePoint-backed import,
  approval-gated transfer/disposal, reports, dashboard, migration, and tests.
- Dedicated Asset Officer, Asset Manager, and read-only auditor boundaries.

### HUB Management

- Existing `stock.*` models retained as the stock ledger.
- Assigned-HUB warehouse/location/quant/lot/picking/move isolation.
- Protected NFI, Medical Equipment, Consumables, and Pharmaceuticals
  categories; lot/serial, quarantine, expiry, FEFO, donor, project, award,
  consignment, operational value, and Asset Register linkage.
- Donor/partner consignments, internal stock requests, partial
  dispatch/receipt, direct external issues/sales/distributions/returns,
  serial-controlled equipment leases, operational collections/reversals, and
  Operations Management-only stock adjustments.
- Stock cannot be reserved until the immutable route is complete and the final
  signed PDF and audit certificate are verified in SharePoint.
- One sequential LHI Sign document per request version. Opening a signing URL
  never approves; only an authenticated provider event for the current frozen
  participant can decide a signature stage.
- Permission-aware dashboard and operational reports.
- Central deduplicated notifications, in-system activities, optional outbound
  mail, bounded retries, resend controls, low-stock/expiry alerts, and Asset
  lifecycle hooks.

The modules do not depend on or create HR employee records, Accounting,
Invoicing, Sales, Rental, accounting valuation, journal entries, invoices,
receivables, or payments. The Accounting feature gate is not applicable because
no Accounting capability is introduced.

## Security and audit controls

- Server-side authorization for actions, RPC methods, provider callbacks,
  scheduled jobs, stock movements, adjustments, reversals, and state changes.
- Company and assigned-HUB record rules plus explicit Director, NED,
  programme, auditor, integration, and ERP administrator scopes.
- Submitted approval lines contain immutable eligible-user snapshots. Later
  matrix edits do not authorize a decision.
- Requester self-approval is denied. Generic approval actions cannot bypass the
  HUB request workflow.
- A process-local object sentinel protects internal context paths; an RPC
  client sending Boolean `True` cannot forge workflow-owned writes.
- Validated transactions and lifecycle histories cannot be silently edited or
  deleted. Corrections use controlled return, superseding version, or reversal.
- Negative stock is blocked. Stock adjustments use a transaction-scoped
  PostgreSQL advisory lock and record before/after quantities and move
  provenance.
- Notification creation is workflow-only. Recipients can access only their own
  queue records; Operations Management and auditors have diagnostics within
  company scope.
- Persistent business-document bytes are delegated to the existing SharePoint
  storage service. Odoo retains relationships, metadata, state, immutable item
  identifiers, hashes, and audit references.

## Configuration, permissions, and secrets

No new environment variable, secret-store entry, Graph permission, or Entra
permission is introduced.

Existing secrets remain in restricted Odoo settings, Coolify environment
configuration, or the approved secret store:

- Microsoft Graph/SharePoint application identity and certificate/secret;
- LHI Sign provider and webhook credentials;
- database and outbound-mail credentials.

Required non-secret configuration:

- company Graph connection and Entra organization mapping;
- SharePoint Operations, Controlled Documents, and Signed Documents library
  mappings, storage policies, content types, webhook, retention, and access;
- protected local recovery administrator accounts;
- Asset category/state codes and one default tag rule per company;
- approved Asset Transfer and Asset Disposal matrices;
- HUB state, office, authorized team, manager/officers, and controlled
  receipt/dispatch/returns/quarantine locations;
- approved HUB request matrices, signer identities, roles, thresholds,
  delegates, and signature coordinates;
- operational payment methods and product low-stock thresholds;
- optional `lhi_hub.expiry_alert_days` system parameter, default 90 and bounded
  to 1–365 days;
- approved SMTP or Microsoft Graph outbound-mail transport, if email is
  required.

SharePoint must fail closed for required artifacts. Tenant/site/library IDs and
credentials must not be committed to Git.

## Schema and migration

The Asset release includes pre/post migration scripts under
`lhi_asset_management/migrations/19.0.2.0.0/`. They detect unsafe duplicates,
preserve legacy identifiers, map statuses/conditions, establish default rules,
and create immutable history.

The HUB release includes an idempotent post-migration under
`lhi_hub_management/migrations/19.0.1.0.0/`. It classifies resolvable existing
categories and backfills lot controlling HUBs only where the current location
is unambiguous. It does not fabricate quantities, tags, approvals, documents,
or accounting data.

Pre-migration checks and post-migration reconciliation must be executed on a
restorable production database copy. Ambiguous legacy lots require an approved
Warehouse Operations mapping.

## Verification actually executed

The following checks passed in this workspace:

- Python compilation of the Asset, HUB, Approval Matrix, and migration code;
- Ruff undefined-name/static checks and format verification;
- Odoo 19 virtual-environment imports of the affected addons and all HUB test
  modules;
- XML well-formedness for addon data, security, views, reports, and Owl
  templates;
- manifest parse and referenced-file existence;
- duplicate XML-ID and ACL-ID checks;
- static resolution of 19 HUB views, 69 record rules, and 91 ACL rows;
- JavaScript ES-module syntax and ESLint checks for both Owl dashboards and
  their Hoot test modules;
- dependency closure across 48 modules with no `hr`, `hr_fleet`, `account`,
  `stock_account`, `sale`, `sale_management`, or `rental` edge;
- forged Boolean context-flag scan; and
- `git diff --check`.

Automated Python and frontend tests were added, but database-backed Odoo tests
were not executed here. No result below may be marked passed until captured
from staging:

- clean install and upgrade of every changed module;
- migration and reconciliation on a database copy;
- non-superuser ACL/record-rule/persona tests;
- PostgreSQL concurrent tag, stock, serial lease, adjustment, and duplicate
  notification tests;
- scheduled-action idempotency and failure isolation;
- Owl/QWeb asset build, browser console, dashboard, drill-down, label, and PDF
  tests;
- LHI Sign success, signer mismatch, replay, duplicate callback, decline,
  timeout, throttling, malformed response, reconciliation, and artifact tests;
- SharePoint upload/download, immutable item ID, hash, permission, webhook,
  retry, and partial-failure tests; and
- clean Coolify image build, backup/restore, health, worker, cron, queue, and
  rollback rehearsal.

Suggested staging commands, adjusted to the approved configuration:

```bash
.venv/bin/python odoo/odoo-bin -c <staging.conf> -d <clean_test_db> \
  -i lhi_hub_management --test-enable \
  --test-tags /lhi_asset_management,/lhi_hub_management --stop-after-init

.venv/bin/python odoo/odoo-bin -c <staging.conf> -d <upgrade_copy_db> \
  -u lhi_security,lhi_asset_management,lhi_programme_asset_bridge,\
lhi_approval_matrix,lhi_hub_management --test-enable --stop-after-init
```

## Manual acceptance evidence

Use the personas and scenarios in the attached requirements and module guides.
At minimum, capture redacted evidence for:

- Entra user without `hr.employee`, protected local administrator, and 14
  requested business personas;
- sidebar/dashboard/menu visibility and absence of HR/Accounting surfaces;
- assigned-HUB and cross-company isolation;
- Asset tag/import/re-tag/transfer/disposal and immutable audit history;
- consignment/pharmaceutical receipt, expiry/quarantine blocking, FEFO, and
  Asset promotion;
- request quantity review, frozen route, three-step signatures, return/reject/
  withdraw/versioning, signed artifacts, reserve, partial dispatch/receipt;
- external free/sale/programme issue, return/reversal, lease release/return/
  overdue/outstanding/reversal, and controlled stock adjustment/reversal;
- missing mail transport, retry/resend/deduplication, low stock, expiry, and
  integration-failure notifications;
- SharePoint previews and Office-for-the-web editing in a new tab; and
- absence of invoices, journal entries, receivables, accounting valuation, and
  production dummy records.

Evidence must redact personal data, tokens, tenant identifiers, document bytes,
provider URLs, and private endpoints.

## Coolify deployment and rollback

Production remains `https://work.lhinigeria.org`.

1. Back up and restore-test the production database and integration
   configuration.
2. Build an immutable image from the approved commit; do not mount editable
   source over it.
3. Add `custom-addons` to the Odoo addons path and retain existing secret
   injection.
4. Run clean-install and upgrade-copy gates before production.
5. Deploy the saved image/version through Coolify, then upgrade only the
   approved modules.
6. Verify health, workers, proxy headers, canonical URL, cron ownership,
   notification/failure queues, provider callbacks, SharePoint health,
   dashboard/menu personas, and logs.
7. Obtain Operations, Security, M365, ERP product-owner, and change approvals
   before declaring go-live.

Rollback is deployment of the prior immutable image/commit plus restoration of
the matching pre-upgrade database backup. Also restore the prior configuration,
disable new crons, revoke/cancel provider signing links created during the
failed window, reconcile SharePoint/webhook/queue state, and verify the prior
application before reopening access. Do not manually delete migrated audit
history or reverse schema changes in place.

## Remaining risks and owners

- Database installation, migration, and test evidence — ERP technical
  lead/QA.
- Concurrent PostgreSQL behavior and performance sizing — ERP technical lead.
- Real HUB/team/matrix/delegation/signer configuration — Operations Director
  and NED.
- Legacy lot mapping and opening reconciliation — Warehouse Operations.
- SharePoint libraries, permissions, webhook, content types, and retention —
  Microsoft 365 administrator and Information Governance.
- LHI Sign provider contract and callback/replay evidence — integration
  administrator and Security.
- Persona acceptance and operational reports — business process owners.
- Coolify backup, restore, rollout, monitoring, and rollback evidence —
  deployment engineer/change manager.

Production approval must remain withheld until these owners supply evidence and
the required stakeholders approve it.
