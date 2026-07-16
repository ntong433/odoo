# LHI Nigeria ERP Discovery and Architecture Pack

Status: **Proposed for stakeholder review**  
Discovery date: **2026-07-15**  
Target: **Odoo 19 Community**  
Scope: architecture and planning only; no business functionality is implemented by this pack.

## Purpose

This pack records the evidence available in the local environment and proposes the functional, technical, security, integration, and delivery architecture for the LHI Nigeria ERP transition.

## Deliverable index

| Requested deliverable | Document |
|---|---|
| Repository/Odoo baseline and current-module inventory | [01-discovery-and-assessments.md](01-discovery-and-assessments.md) |
| Enterprise Accounting assessment template | [01-discovery-and-assessments.md](01-discovery-and-assessments.md#existing-enterprise-accounting-assessment-template) |
| Leave and OpenSign assessments | [01-discovery-and-assessments.md](01-discovery-and-assessments.md#existing-leave-management-assessment) |
| Stakeholders, scope, exclusions, acceptance criteria | [02-functional-architecture.md](02-functional-architecture.md) |
| System context, addon design, dependency map, security/API boundaries | [03-technical-architecture.md](03-technical-architecture.md) |
| Data ownership matrix | [04-data-ownership.md](04-data-ownership.md) |
| Risks, assumptions, Definition of Done, backlog and sprint sequence | [05-delivery-plan.md](05-delivery-plan.md) |
| Architecture Decision Records | [adrs/README.md](adrs/README.md) |
| Changed files, verification and handoff | [06-sprint-summary.md](06-sprint-summary.md) |

## Approval record

This document set is not approved merely because it exists in source control.

| Role | Named approver | Decision | Date | Conditions/notes |
|---|---|---|---|---|
| Executive sponsor | TBD | Pending | — | — |
| Product owner | TBD | Pending | — | — |
| Finance owner | TBD | Pending | — | Accounting boundary and cutover |
| HR/Leave owner | TBD | Pending | — | Leave ownership and integration |
| Procurement/Operations owner | TBD | Pending | — | Operational workflows |
| IT/Security owner | TBD | Pending | — | Identity, RBAC, APIs, hosting |
| Data/BI owner | TBD | Pending | — | Power BI contract and refresh |

## Evidence limitations

- The repository and adjacent Leave/OpenSign source trees were inspected statically; no production database, installed-app export, live configuration, identity tenant, Power BI workspace, network topology, or Enterprise Accounting instance was made available.
- “Present in source” does not mean “installed in an LHI database.” The installed-state inventory remains a discovery action.
- Department names, named stakeholders, approval thresholds, companies, sites, warehouses, asset classes, and reporting SLAs require business confirmation.
- Findings about existing integrations are code-review observations, not penetration-test results.

