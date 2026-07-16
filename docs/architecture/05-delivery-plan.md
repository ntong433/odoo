# 5. Risks, Assumptions, Definition of Done and Delivery Plan

## Initial risk register

Scoring: probability (P) and impact (I), 1–5; score = P × I. Owners are roles until named.

| ID | Risk | P | I | Score | Response/mitigation | Owner |
|---|---|---:|---:|---:|---|---|
| R01 | Enterprise Accounting scope/customizations are unknown | 4 | 5 | 20 | Complete template, data profiling and interface workshops before bridge build | Finance owner |
| R02 | Community Purchase technically installs Accounting, causing accidental use | 4 | 5 | 20 | Fail-closed flag, server guards, restricted groups/menus/jobs and automated denial tests | Architect/Finance |
| R03 | Current OpenSign webhook can be forged/replayed and uses broad elevation | 4 | 5 | 20 | Signed events, allowlists, idempotency, scoped service, queue, security tests | Security/OpenSign owner |
| R04 | Duplicate employee/identity records across Entra, Leave and Odoo | 4 | 4 | 16 | Immutable Entra `oid`, uniqueness constraints, reconciliation and quarantine | HR/Identity owner |
| R05 | Existing Leave API is not a formal versioned integration contract | 4 | 4 | 16 | Define supported service/event API, SLA, scopes, schema/version and recovery | Leave owner |
| R06 | Approval policy/thresholds and SoD are not approved | 4 | 5 | 20 | Control workshops, versioned policy and scenario sign-off before workflow build | Process owners/Audit |
| R07 | Custom addon dependency coupling makes upgrades unsafe | 3 | 4 | 12 | Layered modules/adapters, no cycles, install/upgrade matrix in CI | Technical lead |
| R08 | Power BI direct access leaks private or cross-company data | 3 | 5 | 15 | Curated views/store, service principal, RLS, field allowlist and privacy review | Data/Security |
| R09 | Uncontrolled `sudo()` or UI-only authorization creates access bypass | 3 | 5 | 15 | Threat model, server checks, least privilege and non-admin negative tests | Security/QA |
| R10 | Poor master data undermines migration and reporting | 4 | 4 | 16 | Owners, profiling, duplicates policy, crosswalk and readiness dashboard | Data owners |
| R11 | Scope expansion from Leave application's timesheet/appraisal functions | 3 | 3 | 9 | Explicit exclusion and separate change-control decision | Product owner |
| R12 | Operational rollout disrupts existing finance reconciliation | 3 | 5 | 15 | Parallel controls, interface reconciliation, phased sites/processes and rollback | Programme/Finance |
| R13 | No verified infrastructure/backup/restore baseline | 3 | 5 | 15 | Environment capture, restore drill, RPO/RTO approval and monitoring | IT Operations |
| R14 | Stakeholder availability delays approval and UAT | 4 | 3 | 12 | Named deputies, workshop calendar and decision deadlines | Sponsor/Product owner |
| R15 | Signed document retention/hash evidence is incomplete | 3 | 5 | 15 | Evidence contract, authenticated retrieval, integrity verification and retention policy | Legal/OpenSign owner |

Review risks at least once per sprint and at every architecture/cutover gate.

## Assumption log

| ID | Assumption | Validation owner | Deadline/gate |
|---|---|---|---|
| A01 | Two-week sprints remain approved | Product owner | Before Sprint 1 |
| A02 | Odoo 19 Community commit/image will be frozen for delivery | IT/Architect | Baseline gate |
| A03 | All custom development resides in workspace `custom-addons/` and uses `lhi_` naming | Technical lead | Continuous |
| A04 | Existing Enterprise Accounting remains official until formal migration | Finance sponsor | Cutover gate |
| A05 | Leave application remains authoritative and exposes a supportable interface | HR/Leave owner | Connector design gate |
| A06 | OpenSign supports an authenticated API and can add signed webhook delivery | OpenSign owner | Connector design gate |
| A07 | Entra tenant administration can provide enterprise app, claims/groups and service principals | Identity owner | Identity sprint |
| A08 | Power BI team can consume a curated contract without write-back | Data owner | BI sprint |
| A09 | Multi-company/site requirements and privacy classification will be confirmed | Sponsor/Security | Functional sign-off |
| A10 | Named owners can approve workflows, thresholds and acceptance scenarios | Sponsor | Before domain builds |

## Definition of Done

The project-wide rules in the root `AGENTS.md` apply. For architecture/discovery work, Done additionally means:

- evidence source, observation date and unknowns are recorded;
- current and target states, scope, owner, security boundary and failure behavior are explicit;
- diagrams render and agree with tables and ADRs;
- decisions have status, context, consequences and approvers;
- functional/process owner, Security, Data and affected integration owners review relevant sections;
- acceptance criteria are testable and backlog items are traceable to risks/decisions;
- no secret, production credential, confidential payload or production dummy data appears;
- stakeholder approval is recorded in the pack's approval table.

For implementation sprints, Done additionally requires valid manifests, ACLs/rules, views/actions, constraints, audit/chatter where relevant, Python/Owl tests, install/upgrade verification, administrator/user documentation and an executed-test report. Security tests include unauthorized ORM/RPC/controller calls, isolation and integration replay/failure behavior.

## Product backlog and sprint sequencing

Sequencing is proposed in two-week sprints. Capacity and calendar dates require team confirmation. Accounting migration remains outside the operational release train.

| Sprint | Epics/outcome | Exit acceptance criteria |
|---|---|---|
| Discovery Sprint (this pack) | E00 baseline and architecture | Pack reviewed; unknowns/owners recorded; no business functionality implemented |
| Sprint 1 | E01 environment/CI baseline; E02 identity/RBAC design validation; master-data workshops | Reproducible build/test DB; installed-module export; approved identity/RBAC matrix and data owners |
| Sprint 2 | E03 `lhi_core`, feature flags, base security; E04 Entra SSO/provisioning | Tenant-restricted SSO; deprovisioning and negative tests; Accounting disabled server-side |
| Sprint 3 | E05 reusable approvals; E06 audit foundation | Versioned policy, SoD, delegation/escalation, immutable evidence and permission/workflow tests |
| Sprint 4 | E07 UI shell/dashboard foundation; E08 CRM-to-project initiation | Role-aware shell; duplicate-safe approved opportunity handoff |
| Sprint 5 | E09 project delivery governance | Stage gates, milestones, issues/risks, updates and isolation tests |
| Sprint 6 | E10 procurement request and approval | Approved thresholds/SoD; request-to-RFQ/PO traceability; failure and duplicate tests |
| Sprint 7 | E11 inventory/site operations | Receipt/issue/return/transfer/count flows with location/company isolation |
| Sprint 8 | E12 operational assets; E13 fleet extensions | Unique custody/serial controls, maintenance/fleet workflows and audit evidence |
| Sprint 9 | E14 Leave connector | Read-only projection, Entra mapping, replay/out-of-order/reconciliation tests; no duplicate leave ledger |
| Sprint 10 | E15 OpenSign connector | Signed/idempotent callback, safe artifact retrieval, adapter eligibility and failure tests |
| Sprint 11 | E16 Power BI contract; E17 Enterprise Accounting bridge (reference-only) | Approved dataset/RLS; reconciled interface in test; no accounting posting |
| Sprint 12 | E18 integrated UAT, performance, recovery, training and operational readiness | End-to-end UAT, restore/rollback drill, support runbooks and go-live approval |
| Later gated programme | E19 Accounting assessment, migration rehearsals and cutover | All Accounting exit criteria and formal activation approval satisfied |

## Epic-level backlog

| Epic | Key stories | Architecture acceptance criteria |
|---|---|---|
| E01 Platform baseline | Container/runtime lock, CI, test DB, backups, observability | Immutable versions; repeatable install/upgrade/test; secrets externalized |
| E02 Identity/RBAC | Role workshops, access matrix, company/team scope, access review | Named owner per role; least privilege; no technical-admin shortcut |
| E03 Core/config | External IDs, feature flags, dimensions, common mixins | Namespaced keys; multi-company; fail-closed flags; no production demo data |
| E04 Entra | OIDC login, provisioning, deprovisioning, group mapping, break-glass | Exact tenant/issuer/audience; unique `oid`; disabled account denied |
| E05 Approvals | Policy versions, steps, SoD, delegation, escalation, activities | Server-side transitions; concurrent/duplicate action safe; complete audit |
| E06 Audit | Sensitive event catalogue, retention, export, review UI | Append-oriented; access restricted; correlation IDs; PII policy |
| E07 UI/dashboard | Shell, navigation, dashboard, exception queues | Owl unit tests; accessible/responsive; no authorization delegated to UI |
| E08–09 Projects | Opportunity handoff, initiation, baseline, delivery, closeout | One handoff; gated transitions; linked evidence; closeout blockers |
| E10 Procurement | Request, sourcing, approval, PO/receipt/accounting refs | Threshold/SoD versions; duplicate prevention; reconciled references |
| E11 Inventory | Locations, receipts, issues, transfers, counts | Standard moves/pickings; serialized integrity; isolation and adjustment approval |
| E12 Assets | Register, tag, custody, maintenance, disposal proposal | Unique tag/serial; custody invariant; no financial depreciation posting |
| E13 Fleet | Vehicle, driver/custody, odometer/service controls | Valid state/custody; reminders idempotent; role isolation |
| E14 Leave | Contract, projection, sync/reconcile, capacity display | Leave remains SoR; read-only Odoo projection; full failure matrix |
| E15 OpenSign | Secure request/event/artifact flow and adapters | Authentication, replay defense, idempotency, verified artifact, scoped access |
| E16 BI | Dataset catalogue, semantic contract, refresh/RLS | Field allowlist, source lineage, RLS/privacy and reconciliation |
| E17 Accounting bridge | Master/reference/status mappings and reconciliation | Disabled-by-default; no journals/posting; batch totals and error queue |
| E18 Readiness | UAT, load, security, DR, training, support | Signed acceptance, no critical defects, tested rollback/support |
| E19 Accounting migration | Profiling, mapping, rehearsal, parallel close, cutover | Formal feature activation only after signed exit criteria |

## Discovery sprint acceptance

- All requested deliverables are linked from the architecture index.
- Observed facts are separated from proposals and unknowns.
- Standard Odoo modules and supported extension approaches are identified.
- System/data ownership has a single proposed authority per domain or an explicit pending decision.
- Security and API trust boundaries include authentication, authorization, isolation, idempotency, replay defense and failure recovery.
- Backlog sequence keeps operational go-live ahead of Accounting migration.
- Stakeholders review and either approve, reject with reasons, or assign dated actions for every open decision.

