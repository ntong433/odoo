# LHI ERP Asset Register and HUB Management Audit

Date: 2026-07-29  
Repository: `/home/jay/Documents/odoo`  
Canonical production URL: `https://work.lhinigeria.org`  
Status: audit gate complete; implementation, migration, uninstall, and deployment not yet performed

## 1. Executive finding

The repository contains useful foundations for the requested operational Asset
Register and HUB solution, but the current code is not a safe base for direct
feature expansion without first correcting dependency, identity, security, and
stock-extension defects.

The most important blockers are:

1. Asset, Inventory, Procurement, LHI Sign, and the SharePoint document
   workspace transitively activate `account` through
   `lhi_purchase_request -> lhi_budget_control -> account`.
2. HR decoupling is incomplete. Entra synchronization and manager approval
   still dereference `hr.employee`; some paths contain an undefined `employee`
   variable and will fail at runtime.
3. `lhi_base` loads an XML reference to `hr.menu_hr_root` without depending on
   `hr`. A clean database without HR can therefore fail to install or upgrade
   `lhi_base`.
4. Existing Asset ACLs allow every internal user to create and edit assets and
   transfers. Transfer approval methods do not enforce dedicated server-side
   roles.
5. The Inventory quant override does not match the Odoo 19 core method
   signature and its post-move quant search is not precise enough for
   lot/package/owner/concurrency boundaries.
6. No HUB authorization model, Asset dashboard, HUB dashboard, legacy Asset
   import, pharmaceutical controls, consignment workflow, HUB Stock Request,
   external issue, lease, or operational-revenue workflow currently exists.

No mass uninstall, destructive data migration, production connection, or
deployment was performed.

## 2. Audit scope and evidence

The audit inspected:

- all 65 `lhi_*` manifests;
- the existing custom-addons knowledge graph;
- Asset, Inventory, Operations dashboard, sidebar, security, approval,
  signature, SharePoint, Entra, programme, project, grant, fleet, procurement,
  and deployment code;
- direct and transitive manifest dependencies;
- custom model declarations and stock-model overrides;
- Python syntax and XML well-formedness;
- Git/submodule state and local runtime availability.

Commands executed during this audit included:

```bash
graphify query "Audit the existing LHI asset, inventory HUB, dashboard/sidebar, approval matrix, signature bridge, SharePoint storage, security, operational structure, and HR/accounting dependencies."
python3 -m compileall -q custom-addons
python3 <manifest and transitive-dependency audit>
python3 <XML well-formedness audit>
git status --short --branch
git submodule status
docker compose ps --format json
docker ps --format '{{json .}}'
./odoo/odoo-bin --version
```

Actual audit results:

- Python syntax compilation: **passed**.
- Manifest parse/version/license check: **65 manifests parsed; passed**.
- XML well-formedness: **241/241 files passed** using the standard-library
  parser.
- Odoo registry, install, upgrade, and transaction tests: **not run**. The host
  environment lacks required Python packages (`passlib` is the first reported
  missing package), no database listener is available, and Docker API access is
  denied to the current process.
- Installed-module/database-state audit: **blocked by runtime access**. Compose
  also cannot interpolate without protected `ODOO_MASTER_PASSWORD` and
  `POSTGRES_PASSWORD` values. Secret values were not read or printed.

## 3. Repository and deployment state

- The outer integration repository is on `main` at
  `63c120e9d44 [REM] various: remove and deactivate Human Resources functionality`.
- The `odoo/` submodule is pinned to upstream `19.0` commit
  `4bd64dafecdb4d02e998379bbeac2825f483e5d9` and is in normal detached-HEAD
  submodule state.
- This distinction must be documented: the Odoo core is on 19.0, while the
  outer deployment repository uses `main`.
- The worktree contained pre-existing untracked files, including a knowledge
  graph and local diagnostic artifacts. They were not modified or committed by
  this audit.
- Development Compose publishes PostgreSQL on host port 5435. Production or
  staging must keep PostgreSQL private to the Compose network.
- The staging Compose file is compatible with Coolify and uses
  `https://work.lhinigeria.org`, but defaults `ODOO_WORKERS` to `0`. Production
  worker sizing and health evidence remain required.
- The bootstrap module list currently includes only the core LHI shell,
  security, approval, feature-control, and dashboard modules. It does not
  automatically activate Accounting, HR, Asset, Inventory, or LHI Sign.

## 4. Dependency audit

### 4.1 Prohibited transitive dependencies

| Operational root | Prohibited path |
|---|---|
| `lhi_asset_management` | `lhi_asset_management -> lhi_purchase_order -> lhi_procurement -> lhi_purchase_request -> lhi_budget_control -> account` |
| `lhi_inventory` | `lhi_inventory -> lhi_purchase_order -> lhi_procurement -> lhi_purchase_request -> lhi_budget_control -> account` |
| `lhi_signature_bridge` | `lhi_signature_bridge -> lhi_purchase_order -> lhi_procurement -> lhi_purchase_request -> lhi_budget_control -> account` |
| `lhi_procurement` | `lhi_procurement -> lhi_purchase_request -> lhi_budget_control -> account` |
| `lhi_document_workspace` | `lhi_document_workspace -> lhi_purchase_request -> lhi_budget_control -> account` |

`lhi_dashboard`, `lhi_web_shell`, `lhi_fleet_operations`, and
`lhi_programme_management` do not currently have a prohibited transitive core
dependency.

### 4.2 Accounting modules present in source

Accounting addons remain present and installable in the repository, including
`lhi_accounting_base`, `lhi_budget_control`, `lhi_grant_accounting`,
`lhi_field_cash`, `lhi_multi_currency`, `lhi_withholding_tax`,
`lhi_advance_accounting`, `lhi_ng_edi`, `lhi_migration_tooling`, and
`lhi_ng_hr_payroll`.

Source presence is not evidence of installation. Database access is required to
verify installed state. The operational implementation must neither depend on
nor activate these modules. No Accounting feature flag was changed.

### 4.3 HR dependencies and residual coupling

- `lhi_leave_bridge` directly depends on `hr`. It is an existing integration
  boundary and must not be duplicated. Its user-facing exposure needs a
  deployment-state decision separate from the Asset/HUB implementation.
- `lhi_ng_hr_payroll` depends on both `hr` and `account`; it must remain dormant
  and outside all operational dependency paths.
- `lhi_base/data/deactivate_hr_menus.xml` references `hr.menu_hr_root` although
  `lhi_base` does not depend on `hr`. This is not safe on a clean HR-free
  database.
- `lhi_entra_identity_sync/models/entra_sync_run.py` still reads
  `manager_user.employee_id`, writes employee hierarchy values, references an
  undefined `employee`, snapshots employee fields, and hashes the obsolete
  `create_missing_employee` setting.
- `lhi_entra_identity_sync/models/approval_matrix.py` still resolves the
  requester manager through `request.creator_id.employee_id.parent_id.user_id`.
- The Entra configuration and view still expose `create_missing_employee`.
- Entra already stores the correct HR-free identity relationship:
  `res.users.entra_manager_object_id` and computed
  `res.users.entra_manager_user_id`. These must be authoritative for operational
  manager resolution.

## 5. Existing architecture and reusable components

### 5.1 Organizational and programme models

Reuse:

- `lhi.office` for offices;
- `lhi.department` for operational units/departments;
- `lhi.programme` for programmes;
- `lhi.project` for projects;
- `lhi.award` for grants/awards;
- `lhi.donor` for donors;
- `lhi.funding.source` for funding sources;
- `lhi.activity` and `lhi.workplan.activity` for activities;
- `res.country.state` as the Odoo-native state model, extended with an
  LHI-specific immutable three-character operational code if required;
- `res.users` and `res.partner` for internal users and external recipients.

The current `lhi.project.code` is the nearest existing project abbreviation.
An explicit `asset_tag_abbreviation` should be added rather than changing the
meaning of existing project identifiers.

### 5.2 Asset models

Reuse and extend:

- `lhi.asset`;
- `lhi.asset.category`;
- `lhi.asset.transfer`;
- `lhi.location`;
- optional programme fields in `lhi_programme_asset_bridge`.

Current Asset coverage is minimal: name, simple tag, serial number, category,
custodian, physical location, donor, free-text grant reference, project,
purchase order, acquisition date, warranty expiry, condition, status, company,
and transfer records.

Missing or unsafe behavior:

- tag is generated from a single `ir.sequence` as a generic value;
- no required LHI tag segments, configurable scope, generation metadata,
  immutability, legacy classification, re-tag approval, or previous-tag audit;
- no unique database constraint on `asset_tag`;
- no serial-number duplicate control;
- no acquisition/ownership/funding separation;
- no state, office, HUB, programme, grant relation, currency/value source,
  barcode/QR, document metadata, warranty detail, or dashboard;
- status and condition vocabularies do not match the specification;
- only transfer rows preserve some movement events; direct writes can overwrite
  tracked values without a normalized history snapshot;
- ordinary internal users have create/write access to assets and transfers;
- activation, submission, approval, completion, and cancellation do not enforce
  allowed source states and dedicated roles server-side;
- the Asset app opens a list rather than an overview.

### 5.3 HUB and stock models

Reuse:

- `stock.warehouse` as HUB;
- `stock.location` as storage location;
- `stock.picking`, `stock.move`, and `stock.move.line` for all on-hand changes;
- `product.template`, `product.category`, and `stock.lot` for items,
  categories, lots/batches, expiry, and serials.

Existing `lhi_inventory` adds project/donor fields to moves, pickings, move
lines, and quants. It does not provide HUB configuration, HUB authorization,
protected product categories, operational values, pharmaceutical controls, or
any requested workflow.

Technical defects:

- `_update_available_quantity` does not match the Odoo 19 signature because it
  omits the positional `reserved_quantity` parameter.
- `_action_done` searches a destination quant using only product, location, and
  lot. It omits package, owner, company, and other quant identity dimensions,
  then mutates the first match. This can misattribute stock and is unsafe under
  concurrency.
- Project/donor ownership should be recorded on moves and controlled
  consignment/transaction records. It must not be forced onto an ambiguously
  selected quant.
- No HUB-specific record rules exist; native stock security is the only current
  boundary.

### 5.4 Approval matrix

Reuse:

- `lhi.approval.matrix` and `lhi.approval.matrix.line`;
- `lhi.approval.request`, request lines, history, and delegation;
- the source-model matrix-selection hook;
- deterministic route preparation/snapshot behavior.

Required extensions:

- add HUB Stock Request as an operational document type;
- add HUB/state/category/product/value/project/programme/grant/donor/emergency
  criteria in a HUB-specific extension;
- snapshot one resolved signer per sequential signing stage;
- encode operational roles, named users, groups, and Entra manager/user
  resolution without HR;
- enforce Director of Operations before NED;
- add required/optional and signature-required stage attributes;
- prevent duplicate stages and unsafe route changes;
- require reasons for reject/return and authorize those actions server-side.

Current generic `action_reject` and `action_return_for_correction` do not repeat
the current-approver authorization checks used by `action_approve`. This is a
release-blocking security gap for reuse.

### 5.5 LHI Sign

Reuse `lhi_signature_bridge`; do not create another provider implementation.

Reusable provider contract:

- `lhi.opensign.configuration`;
- `lhi.opensign.request`;
- `lhi.opensign.recipient`;
- `lhi.opensign.webhook.event`;
- HMAC-authenticated public callback;
- provider and idempotency unique constraints;
- sequential recipients and current-recipient checks;
- participant matching by normalized email;
- protected preparation and participant signing URLs;
- source hooks, completion hooks, and event hooks;
- preparation validation with per-recipient required widget types;
- provider reconciliation and duplicate-event handling;
- uncertain provider-creation state;
- revoke/supersede flows;
- signed PDF and audit-certificate capture through SharePoint.

Required adaptations:

- remove the prohibited Accounting dependency path;
- use a HUB-specific deterministic idempotency key containing request ID,
  version, and source PDF hash;
- set `signature,name,date` for every HUB approver, not only a final signer;
- snapshot approval role, signer name/email, provider participant ID, decision,
  comments, and provider timestamp;
- expose “Approve and Sign” only through the authorized HUB request action;
- never expose another recipient's URL;
- make provider copy/notes generic instead of memo-specific;
- add HUB-specific revoke, correction/versioning, and reservation gates.

### 5.6 SharePoint

Reuse `lhi_sharepoint_storage`:

- `lhi.document.item.create_from_bytes(...)` performs permission-aware,
  fail-closed, synchronous upload;
- temporary bytes use a protected spool;
- metadata includes immutable site, drive, and item IDs;
- idempotency, unique DriveItem constraints, retries, dead-letter state,
  bounded cron processing, remote size/hash verification, and reconciliation
  already exist;
- protected download routes re-check linked-record access.

Add storage policies for Asset, Asset import source, HUB Stock Request versions,
dispatch notes, receipt confirmations, consignment documents, external issue
notes, and lease documents. Business models should store `lhi.document.item`
relations and hashes, never permanent large binary payloads.

### 5.7 Dashboard and sidebar

Reusable:

- `lhi.dashboard.widget` backend-generated app entries;
- native `_visible_menu_ids()` check;
- Owl widget registry;
- current custom sidebar and theme/dark-mode assets;
- retry behavior in the main dashboard and isolated error handling in some
  widgets.

Gaps:

- user-facing labels remain “Inventory”, “Assets”, and “Operations Hub” instead
  of “HUB”, “Asset Register”, and “Operations Overview”;
- Accounting remains a static launcher definition;
- optional menu/group XML IDs can still produce an all-or-nothing backend
  failure;
- not all widgets have an Owl error boundary or backend result isolation;
- the Operations card payload uses `icon_url`, while its template reads
  `module.icon`;
- no Asset or HUB operational KPI/chart backend exists;
- dashboard totals do not have HUB/location access domains because HUB
  assignments do not exist.

The dashboard no longer contains an HR launcher definition and Fleet remains in
Operations. That work should be preserved.

## 6. Security audit

Current security must not be expanded by granting Settings or broad
administrator access.

Findings:

- Asset ACLs grant all `base.group_user` members read/write/create access to
  assets and transfers.
- Asset rules only isolate by company; they do not scope by HUB, office,
  project, state, custodian, or Asset role.
- Asset categories and locations are managed through `base.group_erp_manager`
  instead of dedicated Asset Manager configuration rights.
- Inventory has no custom ACLs/rules and no assigned-HUB boundary.
- Existing LHI employee project/office/department rules intentionally return all
  records when a user has no assignments. This is fail-open for newly
  synchronized users and conflicts with least privilege.
- Approval request lines and history are writable/creatable by the broad
  employee group.
- Generic reject/return methods lack current-approver authorization.
- LHI Sign provider URLs are correctly restricted to Signature Administrator,
  but HUB signing must obtain only the current user's URL through a protected
  server method after checking the HUB request and current route stage.

The operational solution requires dedicated groups:

- HUB Viewer;
- Warehouse Officer;
- Operations Officer;
- Operations Manager;
- Director of Operations;
- National Executive Director;
- Asset Officer;
- Asset Manager;
- Programme User;
- Programme Approver;
- System Auditor;
- Stock Adjustment Controller.

No separate Lease Officer group will be created.

## 7. Data and migration audit

Database contents could not be inspected. Before any staging or production
migration:

1. create and verify a PostgreSQL backup and filestore/volume recovery point;
2. export installed module state and dependency state;
3. count existing assets, asset tags, serials, warehouses, locations, categories,
   lots, moves, users, HR-linked users, approval routes, signature requests, and
   SharePoint document items;
4. detect duplicate/conflicting tags, serials, codes, and warehouse mappings;
5. run all migrations on a restored copy;
6. retain legacy identifiers and stop on unsafe ambiguity;
7. verify rollback on a second restored copy.

No migration or uninstall was run during this audit.

## 8. Target module architecture

To avoid duplicate models and preserve upgrade safety:

### Extend existing modules

- `lhi_base`: HR-free operational/state code support only.
- `lhi_security`: dedicated operational roles and assignment fields.
- `lhi_asset_management`: become the production Asset Register by extending
  existing `lhi.asset` models rather than adding a duplicate asset model.
- `lhi_inventory`: become the shared HUB stock extension layer and remove unsafe
  quant mutation.
- `lhi_approval_matrix`: secure generic current-approver transitions.
- `lhi_signature_bridge`: remain the single LHI Sign provider adapter.
- `lhi_dashboard` and `lhi_web_shell`: resilient permission-aware navigation.
- `lhi_entra_identity_sync`: use `res.users.entra_manager_user_id`, never
  `hr.employee`.

### Add bounded operational modules

- `lhi_hub_management`: HUB configuration, authorizations, product/lot
  operational extensions, consignments, and shared movement helpers.
- `lhi_hub_approval`: HUB Stock Request, route snapshot, quantity review,
  versioned PDF, LHI Sign hooks, reservation/dispatch/receipt gates.
- `lhi_hub_external_transactions`: external recipients, issues,
  distributions, leases, returns, payments, and operational revenue.
- `lhi_hub_dashboard`: permission-scoped Asset/HUB KPI and chart services plus
  client actions.
- optional bridge modules only where both sides are installed, such as
  Asset/HUB serialized-equipment linkage.

The suggested `lhi_asset_registry` is not created because `lhi.asset` already
exists. Extending `lhi_asset_management` avoids duplicate assets and preserves
existing identifiers.

## 9. Phased implementation plan

### Phase 1 — release blockers and operational dependency split

- replace Entra/approval employee resolution with synchronized `res.users`;
- remove unsafe HR-menu XML coupling from clean installation;
- separate operational budget-line identity from Accounting so Procurement,
  Asset, Inventory, LHI Sign, and SharePoint workspace do not activate
  `account`;
- correct Inventory Odoo 19 overrides;
- make dashboard/sidebar optional references and widget results fail
  independently;
- add regression tests for users without employee records and accounting-free
  dependency closure.

### Phase 2 — Asset Register foundation

- extend existing Asset/category/location models;
- add configurable tag rule and concurrency-safe scoped sequence allocation;
- add immutable confirmation, legacy preservation, unique tag/serial
  constraints, re-tag approval/history, movement history, lifecycle transitions,
  operational value, and SharePoint document relations;
- implement dedicated roles, ACLs, record rules, views, labels, reports, and
  overview action;
- add CSV/XLSX import batches, preview rows, validation, error report, rollback
  gates, and source-file SharePoint preservation.

### Phase 3 — HUB foundation and consignment

- extend `stock.warehouse` as HUB with state/office/authorized users and special
  locations;
- add HUB-scoped security rules and protected operational categories;
- add operational unit values without `stock_account`;
- extend lots for pharmaceuticals, donor/consignment/project/grant,
  manufacturing/expiry/removal dates, quarantine, temperature, and FEFO;
- add expired/quarantined issue blocking;
- add consignment receipt/inspection/discrepancy workflow using validated stock
  pickings only.

### Phase 4 — HUB Stock Request, approval, LHI Sign, and SharePoint

- implement request, lines, quantity review, route snapshot, approval snapshot,
  and document versions;
- extend matrix criteria and enforce Director of Operations before NED;
- generate one immutable PDF per version with all request lines and approval
  blocks;
- set and validate Signature/Name/Date for every signer;
- use one existing LHI Sign request and strict webhook/reconciliation evidence;
- store source/final/certificate in SharePoint;
- reserve only after all required provider-confirmed signatures;
- support partial dispatch/receipt and audited close balance.

### Phase 5 — external operations

- implement data-minimized external recipients;
- implement multi-item issues, free issues, distributions, sales, returns, and
  reversals without approval matrices or LHI Sign;
- implement leases managed by Warehouse Officers, serial availability,
  release/return/inspection, charges, waivers, and payments;
- implement operational revenue without invoices, journals, ledgers, or
  Accounting records.

### Phase 6 — dashboards, reports, migration, and release evidence

- implement Asset and HUB overview cards/charts with permission-aware drilldown;
- complete Operations and Programmatic Operations navigation labels;
- add printable operational reports;
- add idempotent migrations and reconciliation;
- run persona, concurrency, browser, provider-contract, SharePoint, clean
  restart, module upgrade, and Coolify rebuild tests;
- publish deployment, rollback, post-deployment validation, and remaining-risk
  evidence.

## 10. Go/no-go controls

The following remain **no-go** until a database copy and protected runtime are
available:

- module uninstall;
- accounting/HR dependency-state changes in a live database;
- data migrations;
- production/staging module upgrades;
- SharePoint/LHI Sign live contract tests;
- Coolify deployment.

Code-only, non-destructive custom-addon development and automated tests against
an isolated new test database may proceed after this audit gate.

## 11. Audit commit and change summary

Changed by this phase:

- added this dependency and architecture audit report only.

Models/fields/schema:

- none.

Environment variables/secrets:

- none.

Microsoft Entra/Graph permissions:

- none changed. Existing least-privilege review remains required before
  deployment.

SharePoint configuration:

- none changed.

Rollback:

- revert the audit-document commit; no database or external state was changed.

Remaining risk:

- installed module state, actual database data, production permissions,
  provider contract, and deployment health cannot be asserted without the
  protected staging environment and a verified backup.
