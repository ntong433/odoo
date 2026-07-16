# 2. Functional Architecture

## Department and stakeholder register

Names must be assigned during validation workshops.

| Stakeholder/department | Accountable interests | Required decisions |
|---|---|---|
| Executive sponsor | Outcomes, funding, priority, cutover risk | Scope and go-live approval |
| Product owner/PMO | Backlog, cross-department process, acceptance | Process baseline and sprint acceptance |
| Programmes/Projects | Opportunity handoff, planning, delivery, closeout | Project lifecycle, stage gates, evidence |
| Business Development/Partnerships | Leads, opportunities, donors/partners | Qualification and handoff criteria |
| Procurement | Requests, sourcing, evaluation, PO process | Thresholds, approvers, exceptions |
| Stores/Inventory | Receipts, issues, transfers, counts, traceability | Warehouses, locations, custody rules |
| Administration/Assets | Equipment registry, custody, maintenance | Asset classes and assignment controls |
| Fleet/Logistics | Vehicles, drivers, trips, fuel/service evidence | Fleet roles, approvals and KPIs |
| Human Resources | Employees, departments, Leave integration | Employee projection and Leave contract |
| Finance | Accounting system, budgets, vendor/payment status | Transition interface and feature gate |
| Internal Audit/Compliance | Audit trail, SoD, retention, evidence | Control catalogue and retention |
| IT Operations | Environments, support, recovery, monitoring | Deployment and operational readiness |
| Information Security/DPO | Identity, access, privacy, integrations | Threat model, RBAC and data classification |
| Data/MEAL/Power BI | KPI definitions, semantic model, data quality | Dataset contract, refresh, RLS |
| OpenSign owner | Signature templates, evidence, service SLA | API/security and artifact retention |
| Leave application owner | Leave API, balances and approvals | Integration SLA and change management |
| Odoo Enterprise partner/owner | Accounting customizations and data | Assessment access and migration support |
| End-user representatives | Usability and operating procedures | UAT scenarios and adoption |

## Functional scope

### In scope for the target programme

1. **LHI shell and dashboard:** coherent navigation, role-sensitive landing experience, operational KPIs and exception queues.
2. **Identity and RBAC:** Entra SSO, controlled provisioning/deprovisioning, department/company assignment, business roles, delegated administration and access reviews.
3. **Reusable approvals:** configurable, versioned approval routes; sequential/parallel steps where approved; delegation, escalation, rejection, withdrawal and evidence.
4. **Audit:** tracked business events, approval history, security events, integration evidence, retention and export to operational monitoring/SIEM if approved.
5. **Opportunity to project closeout:** qualification, award/handoff, project initiation, team and site/donor dimensions, milestones, tasks, risks/issues, procurement/stock links, periodic updates, acceptance and closeout checklist.
6. **Procurement:** purchase request, sourcing/RFQ reference, evaluation evidence, approvals, PO handoff, receipt status and accounting references without replacing Enterprise Accounting.
7. **Inventory:** product master governance, warehouses/locations, receipts, internal transfers, issues/returns, lots/serials where needed, counts and project/site consumption.
8. **Operational assets:** equipment registration from receipt, tag/serial, custody, assignment/return, maintenance, transfer and retirement proposal. Financial capitalization/depreciation remains excluded pre-cutover.
9. **Fleet:** vehicle master, custody, driver assignment, odometer, service/contract reminders and approved operational requests; detailed trip/fuel scope requires validation.
10. **Leave integration:** read-only availability/absence projection from the existing Leave system.
11. **OpenSign:** configured final-signature requests and verified status/artifact return for approved document types.
12. **Power BI:** governed, read-only operational datasets for portfolio and executive analytics.
13. **Dormant Accounting:** architecture and disabled modules/contracts for a later controlled migration.

## Explicit exclusions for the operational go-live

- Rebuilding Leave requests, balances, types or approvals in Odoo.
- Replacing Microsoft Entra ID or operating an independent employee identity directory.
- Replacing OpenSign signature execution or Power BI analytics.
- Migrating, posting or reconciling production accounting in the new ERP.
- Payroll processing, donor-specific functions, statutory reporting, banking/payment execution and financial asset depreciation unless separately approved.
- Unapproved core modifications, direct database integrations, production dummy data, or a broad data migration beyond signed scope.
- Timesheet and performance-appraisal migration from the Leave application; these require separate decisions.

## End-to-end target processes and acceptance criteria

### Opportunity to closeout

Flow: `Opportunity qualified → award/handoff approved → project initiated → baseline approved → delivery/updates → operational acceptance → closeout approved → archived`.

Acceptance criteria:

- A project cannot be created from an opportunity twice; the source opportunity and award evidence remain traceable.
- Stage transitions enforce required fields, role, company and approval server-side.
- Project, procurement, stock, asset and signature records link through stable relational references.
- Closeout is blocked until required deliverables, open commitments, custody returns and final approvals are resolved or explicitly waived by an authorized role.

### Procurement to receipt

Flow: `Request → validation → approval → sourcing/RFQ → evaluation → PO authorization → receipt → accounting-reference synchronization`.

Acceptance criteria:

- Requester cannot approve their own request where SoD requires separation.
- Threshold and dimension rules use the approved policy version effective at submission.
- PO confirmation and receipt are independently authorized and auditable.
- Integration failures do not duplicate POs, receipts or Enterprise Accounting references.

### Inventory and custody

Flow: `Receipt → inspect/accept → store → issue/assign/transfer → return/count/maintain → disposal proposal`.

Acceptance criteria:

- Stock operations use standard pickings/moves and enforce company/location access.
- Serialized items cannot have conflicting custody; adjustments require reason and authorization.
- Financial asset treatment is never inferred or posted while Accounting is disabled.

### Final signature

Flow: `Eligible approved document → immutable rendition/hash → signature request → OpenSign execution → verified callback/poll → signed artifact and certificate attached → business transition`.

Acceptance criteria:

- Only authorized users and eligible states can request signature.
- Duplicate requests/callbacks are idempotent; forged, expired and replayed callbacks are rejected and audited.
- Signature completion cannot be asserted solely from client input or an unauthenticated URL.

