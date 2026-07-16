# 1. Discovery and Current-State Assessments

## Repository and Odoo 19 baseline

| Item | Observed baseline |
|---|---|
| Core checkout | `/home/jay/Documents/Odoo/odoo` |
| Remote | `https://github.com/ntong433/odoo.git` |
| Branch | `19.0`, tracking `origin/19.0` |
| Inspected commit | `4bd64dafecdb4d02e998379bbeac2825f483e5d9` |
| Commit date/subject | 2026-07-15; `[REM] pos_self_order: remove obsolete self_ordering_mode check for 'qr_code'` |
| Runtime release | `version_info = (19, 0, 0, FINAL, 0, '')` |
| Supported Python declared by source | 3.10 through 3.14 |
| Minimum PostgreSQL declared by source | 13 |
| Addon manifests in `odoo/addons` | 630 |
| Framework addon manifests in `odoo/odoo/addons` | 24 |
| Worktree observation | Untracked `odoo/addons/opensign_odoo/`; no tracked core modification observed |
| Target custom path | Workspace-level `custom-addons/`, outside the core checkout |

### Baseline conclusions

1. The checkout is a current Odoo 19 Community source baseline, but reproducibility is incomplete until Python, PostgreSQL, OS/container image, dependency lock, addons path, configuration, and database extensions are recorded.
2. The source tree is broad; deployment must use an explicit allowlist of installed modules rather than assuming every source addon is part of the solution.
3. `opensign_odoo` is a prototype located contrary to the target extension policy. It is retained as discovery evidence and should later be replaced or migrated into a namespaced `custom-addons/lhi_opensign` module through a reviewed migration—not moved during this sprint.
4. A clean baseline tag or immutable image digest must be approved before implementation begins.

### Required environment capture before Sprint 1 closes

- OS/container image digest, Python patch version, PostgreSQL version and extensions.
- `odoo.conf` shape with secrets redacted, complete `addons_path`, worker/cron/proxy settings, filestore and backup design.
- Database list, company list, languages, currencies, time zones, mail gateway, object storage, and installed module export.
- CI pipeline, test database lifecycle, lint/static-analysis tools, artifact registry, deployment promotion and rollback procedure.
- Environment matrix for development, test, UAT, staging and production, including demo-data policy.

## Current-module inventory

“Source status” below is confirmed from manifests. “Installed status” is unknown until a database export is supplied.

| Capability | Standard addon(s) present | Principal records/extension surfaces | Proposed use | Installed status |
|---|---|---|---|---|
| Opportunity | `crm`, `sale_crm` | `crm.lead`, `crm.team`, stages, activities, chatter | Opportunity and qualification source | Unknown |
| Sales handoff | `sale`, `sale_project` | `sale.order`, order lines, project generation hooks | Controlled opportunity-to-project handoff; not accounting ownership | Unknown |
| Project delivery | `project`, `project_todo` | `project.project`, `project.task`, milestones, roles, updates, portal | Extend for initiation through closeout | Unknown |
| Procurement | `purchase`, `purchase_stock` | `purchase.order`, `purchase.order.line`, RFQ actions, vendor/product hooks | Extend with request, approval and budget-reference controls | Unknown |
| Inventory | `stock`, `project_stock` | warehouses, locations, pickings, moves, quants, lots, replenishment | Operational stock system of record | Unknown |
| Physical assets/equipment | `maintenance`, `stock` | `maintenance.equipment`, requests, product/serial/lot records | Equipment registry and maintenance; do not confuse with financial assets | Unknown |
| Fleet | `fleet` | vehicles, models, drivers, contracts, odometers, services/costs | Operational fleet registry | Unknown |
| Employees | `hr` | employee/private-public views, departments, jobs, work locations, users | ERP employee projection keyed to Entra identity | Unknown |
| Contacts | `contacts`, `base`, `mail` | `res.partner`, addresses, followers and activities | Vendors, donors, partners and customer contacts | Unknown |
| Authentication | `auth_oauth`, `auth_ldap`, `auth_signup` | OAuth provider, login flow, user provisioning hooks | Entra OIDC/OAuth SSO; local emergency access controlled | Unknown |
| Leave | Standard `hr_holidays` present; separate LHI Leave application also present | Odoo `hr.leave*`; external REST APIs and Supabase tables | Integrate external Leave; do not implement a second leave ledger | Unknown |
| Mail/audit collaboration | `mail`, `bus` | `mail.thread`, activities, messages, subtypes, notifications | Chatter, approvals evidence, activities, notifications | Unknown |
| Reporting | standard list/pivot/graph/report actions; `spreadsheet_dashboard`, `board` | reporting models, actions, export/API surfaces | Operational reporting in Odoo; curated analytics in Power BI | Unknown |
| Web client | `web`, Owl registries/assets/services/client actions | `web.assets_backend`, registry categories, services, actions | Namespaced LHI shell/dashboard extensions | Unknown |
| Accounting technical layer | `account`, `analytic`; `purchase` depends on `account` | moves, journals, analytic accounts/plans | Technical dependency only until approved migration; posting disabled by feature gate | Unknown |
| Generic approvals | No standard `approvals` addon observed | N/A | Implement reusable `lhi_approval` workflow rather than rely on an absent addon | N/A |
| Generic immutable audit addon | No `auditlog` addon observed | N/A | Implement targeted LHI audit events plus chatter; assess SIEM export | N/A |
| Existing custom prototype | `opensign_odoo` (untracked) | `opensign.document`, sale-order extension, settings, public webhook | Assessment input only; not production-ready | Not established |

## Relevant Odoo extension-point assessment

| Area | Supported extension approach |
|---|---|
| Models/workflows | `_inherit`, delegated composition where appropriate, ORM overrides with `super()`, constraints, tracked fields and explicit action methods |
| Project | Extend `crm.lead`, `project.project`, `project.task`, milestones, project updates and sale/project handoff; avoid replacing standard stages/tasks |
| Purchase | Extend purchase orders and lines; add separate purchase-request model; hook confirmation/state actions server-side; preserve stock integration |
| Inventory | Extend picking/move/product/lot/equipment models; configure routes, warehouses and operation types; never write quants as a business shortcut |
| Fleet/assets | Extend fleet and maintenance records with custody/project/site links; keep financial depreciation outside the operational asset registry |
| Employees/contacts | Extend `hr.employee`, `hr.department`, `res.users`, `res.partner`; use immutable external identity keys and multi-company rules |
| Authentication | Configure/extend OAuth provider and login/provisioning callbacks; validate tenant, issuer, audience and account status server-side |
| Reporting | Odoo search/list/pivot/graph/QWeb for operational needs; stable, read-only curated export contract for Power BI |
| Mail/audit | `mail.thread`, `mail.activity.mixin`, subtypes and scheduled activities; dedicated append-oriented audit events for sensitive actions |
| Web client | Owl components, templates, services, client actions and namespaced registry keys in standard asset/test bundles; minimize global patches |

## Existing Enterprise Accounting assessment template

Complete this against the live Enterprise instance with Finance, auditors and the implementation partner. Do not record credentials in the document.

### Instance and governance

| Question | Evidence/answer | Owner | Status |
|---|---|---|---|
| Enterprise version, edition, hosting and database identifier? | TBD | IT/Finance | Open |
| Legal entities, branches, fiscal positions and base/transaction currencies? | TBD | Finance | Open |
| Chart of accounts and Nigeria localization configuration? | TBD | Finance | Open |
| Fiscal calendars, lock dates and close procedure? | TBD | Finance | Open |
| Named process/data owners and segregation-of-duties matrix? | TBD | Finance/Security | Open |
| Integration, reporting, backup, retention and audit obligations? | TBD | IT/Audit | Open |

### Functional inventory

Capture: GL, AP, AR, cash/bank, taxes, budgets, analytic accounting, expense, fixed assets, payroll postings, intercompany, multi-currency, payment approvals, reconciliation, statutory reports, custom reports, journals, sequences and period close.

For each capability record: enabled modules, customization, volume, data quality, owner, upstream/downstream integrations, controls, exceptions, statutory retention and migration disposition (`retain`, `archive`, `migrate`, `replace`, `retire`).

### Interface and reconciliation template

| Flow | Source owner | Target owner | Frequency | Control total | Error owner | Replay key | Cutover disposition |
|---|---|---|---|---|---|---|---|
| Approved PO/commitment reference | New ERP | Enterprise Accounting | TBD | Count/value by currency | TBD | TBD | Define |
| Vendor/bill reference | Define | Define | TBD | Count/value/tax | TBD | TBD | Define |
| Payment/status reference | Enterprise Accounting | New ERP | TBD | Count/value/status | TBD | TBD | Define |
| Project/analytic dimensions | Define | Define | TBD | Dimension counts | TBD | TBD | Define |

### Accounting exit criteria

- Signed source-to-target mapping and opening-balance strategy.
- Reconciled trial balance, subledgers, taxes, bank, receivables, payables and retained history.
- Approved segregation of duties, journal controls, lock dates and audit evidence.
- Two successful dress rehearsals, performance evidence, backup/restore and tested rollback.
- Formal Finance, Audit, Security and executive cutover approval before enabling `lhi_accounting_enabled`.

## Existing Leave Management assessment

### Observed

- Separate application at `/home/jay/Documents/Leave Application` using Next.js 16/React 19, Supabase and Microsoft libraries.
- Entra object ID (`oid`) is used as the authoritative identity key; API caller resolution validates the access token through Microsoft Graph `/me`.
- Supabase tables/migrations include leave requests, types, balances, sequential approval steps, approval tokens and audit data with row-level-security policies.
- APIs cover submit/list, approve/reject, balances, administrative maintenance, reminders, directory lookup and notifications.
- Approval logic validates the current approver and uses a database RPC for the approval transition/balance deduction.
- The same application also contains timesheet and appraisal capabilities; integration scope must not accidentally absorb those domains.

### Proposed integration contract

- Leave application remains system of record for requests, balances, leave types, approval steps and leave audit history.
- Entra remains identity/directory owner. Map Entra `oid` to a unique, indexed Odoo employee/user external identifier.
- Odoo consumes only approved/rejected/cancelled absence summaries needed for capacity, project planning and display. It must not recompute balances or approve leave.
- Prefer a versioned service API or outbound event feed from Leave. Do not connect Odoo directly to Supabase tables.
- Use external leave request ID plus event version as idempotency key. Maintain sync cursor, received-at time, payload hash, status and retry metadata.
- Resolve conflicts in favor of Leave; Odoo projections are read-only to business users.

### Open questions and acceptance evidence

- API ownership, versioning, service identity, scopes, webhook availability, rate limits and support SLA.
- Cancellation/retroactive-change behavior, public holidays, time zones and partial days.
- Employee termination/identity-change behavior and manager/department history.
- Prove duplicate, out-of-order, replay, deletion, timeout, malformed response and recovery handling.

## OpenSign integration assessment

### Observed prototype

- `opensign_odoo` depends on `base`, `mail`, and `sale`; it creates `opensign.document`, extends sale orders, stores settings and accepts `/opensign/callback` as `auth='public'`, CSRF-disabled.
- OpenSign `DocumentAftersave.js` sends created/completed/declined/signer-step callbacks with document and Odoo record references.
- Callback requests currently carry JSON only; no signature, timestamp, nonce or explicit idempotency header is evident.
- Odoo callback searches and writes with broad `sudo()`, logs callback payloads, and may download a URL supplied by the callback.
- ACLs give all internal users create/write/read access and use `base.group_system` as manager. There are no record rules, dedicated groups, unique constraints, explicit transition constraints or automated tests.
- Configuration/XML/model identifiers do not follow the required `lhi_` namespace. Password/master-key handling needs a formal secrets design.

### Target contract and remediation requirements

- Replace with `lhi_opensign` in `custom-addons`; preserve/migrate prototype records only after data mapping and approval.
- Odoo owns signature requests and business-record links; OpenSign owns signature execution, signer evidence, signed artifacts and certificates.
- Use OAuth2 client credentials or a dedicated service credential stored outside source; use HMAC or asymmetric webhook signatures with timestamp, nonce and bounded replay window.
- Use an allowlisted callback URL configured server-side; do not accept arbitrary callback destinations from document data.
- Store a unique request ID, OpenSign document ID, event ID/version, payload hash and state-transition log. Acknowledge duplicates without applying twice.
- Validate document ownership and allowed state transition before scoped elevation. Never trust callback model names or record IDs to select arbitrary Odoo records.
- Queue outbound sends and artifact downloads; enforce HTTPS, host allowlist, size/type limits, timeouts, retry/backoff and dead-letter review.
- Fetch signed artifacts through an authenticated OpenSign API, verify expected document hash where supported, and attach immutable evidence to the authorized business record.
- Add security, workflow, constraint, duplicate, replay and failure-path tests before production use.

