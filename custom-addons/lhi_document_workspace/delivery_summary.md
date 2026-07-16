# Modification Sprint 4 delivery summary

## Outcome

Implemented `lhi_document_workspace` for native, permission-aware SharePoint
document browsing and preview in Odoo 19 Community, with Microsoft 365 editing
in a new browser tab.

Existing LHI RBAC, record rules, project scope, workflow state, segregation of
duties, and protected administrator roles remain authoritative. Interactive
Microsoft operations use delegated user identity. No anonymous sharing links,
tenant-wide Graph permissions, new RBAC groups, Odoo core changes, or
business-document byte storage were introduced.

## Changed files

New `lhi_document_workspace` files:

- `README.md`, `delivery_summary.md`, `__init__.py`, `__manifest__.py`
- `controllers/__init__.py`, `controllers/workspace.py`
- `models/__init__.py`, `models/audit_log.py`, `models/document_item.py`,
  `models/document_template.py`, `models/storage_policy.py`,
  `models/workspace_mixin.py`
- `security/ir.model.access.csv`,
  `security/lhi_document_workspace_security.xml`
- `data/storage_policy_data.xml`
- `views/document_item_views.xml`, `views/document_template_views.xml`,
  `views/document_workspace_views.xml`, `views/storage_policy_views.xml`,
  `views/lhi_document_workspace_menus.xml`
- `static/src/js/document_workspace.js`
- `static/src/xml/document_workspace.xml`
- `static/src/scss/document_workspace.scss`
- `static/tests/document_workspace.test.js`
- `tests/__init__.py`, `tests/test_document_workspace.py`
- `docs/administrator_guide.md`, `docs/user_guide.md`,
  `docs/deployment_and_rollback.md`

Existing files corrected for Odoo 19 compatibility or linked-record security:

- `lhi_fleet_operations/views/menu_views.xml`
  - updated the obsolete Fleet menu parent XML ID;
- `lhi_inventory/views/lhi_stock_move_views.xml`
  - updated the obsolete stock picking move-field XPath; and
- `lhi_sharepoint_storage/models/document_item.py`
  - replaced an invalid Odoo 19 environment cache lookup with registry/model
    lookup so delegated linked-record authorization is actually evaluated.

No Odoo core file was changed.

## New models and fields

### New model: `lhi.document.template`

Fields:

- `name`, `active`, `sequence`, `company_id`
- `graph_connection_id`, `model_name`, `file_type`
- protected `source_drive_id`, protected `source_item_id`
- `source_name`, `source_mime_type`, `source_size`
- `state`, `validated_at`, `validated_by_id`, `last_error`

The source DriveItem is unique per company and target business model.
Administrators have full access; internal auditors have read-only access;
ordinary users have no direct ACL.

### Extended model: `lhi.document.storage.policy`

- `workspace_enabled`
- `workspace_lock_states`

### Extended business models

A non-stored computed Boolean field named `lhi_document_workspace` is added
through `lhi.document.workspace.mixin` to:

- `lhi.project`
- `lhi.funding.opportunity`
- `lhi.proposal.workspace`
- `lhi.award`
- `lhi.workplan`
- `lhi.meal.data`
- `lhi.meal.evidence`
- `lhi.project.report`
- `lhi.partner.profile`
- `lhi.subaward`
- `lhi.purchase.request`
- `lhi.sourcing`
- `lhi.purchase.order`
- `lhi.receipt`
- `stock.picking`
- `stock.lot`
- `lhi.asset`
- `fleet.vehicle`
- `lhi.fleet.trip`
- `lhi.fleet.incident`
- `lhi.reporting.calendar`
- `lhi.project.closeout`

### Extended audit event types

- `document_preview`
- `document_edit`
- `document_download`
- `document_version`
- `document_archive`
- `document_create`
- `document_link_copy`

## Implemented behavior

- default inline preview through a fresh delegated Graph preview action;
- Word, Excel, and PowerPoint browser editing in a synchronously opened new tab;
- preservation of the original Odoo record when popups are blocked;
- Office desktop protocol links;
- delegated secure download and existing governed SharePoint links;
- bounded version history using the Graph pagination helper;
- direct-browser existing-item upload sessions without Graph-token exposure;
- sequential chunk resumption, five transient retries, exponential backoff,
  `Retry-After`, and per-request timeout;
- immutable item ID, active-session, changed-ETag, file-policy, hash, metadata,
  and DriveItem verification before version availability;
- SharePoint recycle-bin archive with ETag precondition;
- model- and company-scoped approved Office templates;
- delegated, idempotent, fail-closed creation from a SharePoint template;
- focus/visibility-return metadata refresh and newer-version notification;
- record- and permitted-project-scoped search with a hard server limit;
- field-level and linked-record authorization checks under the current user;
- workflow-lock enforcement;
- multi-company template rule;
- audit events for all important user actions; and
- responsive Owl UI using existing LHI design tokens.

## New environment variables

None.

Existing Graph client-secret/configuration variables and
`LHI_SHAREPOINT_SPOOL_DIR` remain required.

## Required Entra permissions

No broader permission than the approved foundation is required:

- application Microsoft Graph `Sites.Selected`, explicitly assigned only to
  the approved LHI ERP SharePoint site with the required write role;
- delegated `Sites.Selected`, `openid`, `profile`, and `offline_access`, with
  actual users permitted on the approved SharePoint resources.

Do not grant tenant-wide `Files.ReadWrite.All`, `Sites.ReadWrite.All`, or
anonymous sharing capability.

## Required SharePoint configuration

- validated LHI ERP site and target libraries;
- explicit selected-permission assignment;
- versioning and recycle bin enabled;
- Office browser editing available;
- approved Word, Excel, and PowerPoint template DriveItems;
- existing LHI metadata columns and retention values;
- no anonymous sharing dependency;
- project/library permission boundaries aligned with Odoo business scope; and
- Odoo CSP `frame-src` allowance for the tenant's Microsoft preview hosts when
  an explicit CSP is deployed.

## Database migration

Normal module install/upgrade creates the new template table, mail/activity
relations, policy fields, view metadata, audit selection values, and six
deterministic storage-policy records.

No custom SQL migration, attachment migration, SharePoint content move, or
production data rewrite is required.

## Automated test evidence

Executed on `lhi_erp_test`:

```text
python3 /opt/odoo/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf \
  -d lhi_erp_test \
  -u lhi_document_workspace \
  --test-enable \
  --test-tags /lhi_document_workspace \
  --stop-after-init
```

Result:

```text
11 post-test methods in 1.25s
13 tests in Odoo statistics
0 failed, 0 errors
1008 queries
```

Coverage includes:

- bounded record/project scope;
- readonly preview and denied edit;
- read-only auditor denial for template approval;
- delegated edit and audit identity;
- workflow-lock denial;
- safe and unsafe preview URLs;
- workspace policy disablement;
- focus-return newer-version detection;
- bounded Graph version pagination;
- template ACL and model scope;
- delegated/idempotent/fail-closed template creation;
- immutable item ID and policy validation; and
- changed-ETag requirement for version confirmation.

Additional executed checks:

- clean standalone module installation: passed;
- module upgrade: passed;
- Python bytecode compilation: passed;
- JavaScript syntax checks with Node: passed;
- backend asset bundle compilation: HTTP 200;
- unit-test asset bundle compilation: HTTP 200, 13,756,322 debug bytes;
- XML/view loading across the 91-module dependency registry: passed; and
- secret-pattern scan of Sprint 4 and compatibility changes: no embedded
  tenant secret, private key, Graph token, SharePoint credential, or production
  database credential found.

The four Owl/Hoot helper tests were executed with host Chromium 150 against the
isolated Odoo test server:

```text
@lhi_document_workspace/document_workspace
4 passed / 4, 0 failed, 11 ms
Test suite succeeded
```

The test-only asset bundle also includes Odoo's QUnit and legacy helper aliases
because the already-installed `lhi_web_shell` and `lhi_dashboard` tests still
import those aliases during the shared Hoot dry run. Production backend assets
are unaffected.

## Manual test evidence

- Confirmed module installation and upgrade on the isolated test database.
- Confirmed all security, data, form-view, template, policy, and menu XML loaded.
- Confirmed backend and unit-test asset bundles compile from the running Odoo
  service.
- Confirmed all four workspace Hoot helpers pass in headless Chromium.
- Confirmed the installed test registry contains 23 workspace fields, 24
  workspace-related views, 35 enabled storage policies in total, and zero
  template records after test rollback; no template/demo business data was
  loaded.
- Live Microsoft preview, co-authoring, desktop Office launch, delegated
  download, template creation, throttled upload, and focus-return behavior were
  not executed because no tenant credentials or production data were used.
- A staging manual-test checklist is supplied in
  `docs/deployment_and_rollback.md`.

## Deployment instructions

See `docs/deployment_and_rollback.md`. Upgrade
`lhi_fleet_operations`, `lhi_inventory`, and `lhi_sharepoint_storage` before
installing/upgrading `lhi_document_workspace`, then redeploy Odoo through
Coolify and validate at `https://work.lhinigeria.org`.

## Rollback procedure

Disable `workspace_enabled` on affected policies first. This blocks workspace
listing, preview, and version confirmation without deleting SharePoint files.
Then revert the application image and restore/upgrade only from an approved
database restore point. Reconcile remote items or versions created after the
snapshot by immutable DriveItem ID and audit reference.

Do not delete SharePoint documents, grant broader Graph permission, or
introduce permanent local storage during rollback.

## Remaining risks

- Live tenant conditional access, delegated `Sites.Selected`, preview iframe,
  and SharePoint permission-boundary behavior require staging evidence.
- Browser co-authoring and Office desktop URI handling vary by managed-browser
  and workstation policy.
- The shared Hoot bundle still depends on legacy helper aliases for pre-existing
  `lhi_web_shell` and `lhi_dashboard` tests; those tests should eventually be
  migrated to native Odoo 19 Hoot helpers.
- Direct browser upload URLs are short-lived; a user may need to select the
  source file again after a fully expired session.
- The dependency registry logs pre-existing warnings for missing manifest
  authors, unsupported `tracking` parameters on `stock.move`, duplicate Project
  labels on `stock.picking`, and legacy `_sql_constraints`.
- A database rollback after a completed remote operation can leave a newer
  SharePoint version or item not represented in the restored database;
  immutable IDs and audit correlation must be reconciled.
