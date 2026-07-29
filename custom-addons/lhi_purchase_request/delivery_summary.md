# Sprint 15 Delivery Summary: Purchase Requests and Operational Budget Commitments

## 2026-07-29 operational dependency correction

`lhi.budget.line` is now owned by the operational Purchase Request module. The
Accounting-only `lhi_budget_control` module optionally extends that model when
the dormant Accounting capability is deliberately installed. Purchase Request,
Procurement, Asset, HUB/Inventory, LHI Sign, and SharePoint workspace dependency
closures therefore no longer activate `account`.

The operational budget value does not create journal entries, invoices,
payments, or accounting valuation. No database migration was executed; a
backed-up database-copy upgrade must verify existing multi-company budget-line
company and currency values before deployment.

## Objectives Met
Successfully implemented the `lhi_purchase_request` and `lhi_procurement_commitment` modules to launch the first end-to-end procurement workflow, providing seamless routing, budget checking, and automated commitment generation.

## Models and Features
### 1. Purchase Request (`lhi_purchase_request`)
- **Budget Lines (`lhi.budget.line`)**: Created to handle operational budget line definitions, tracking descriptions, projects, cost centers, and total initial budgets.
- **Purchase Request (`lhi.purchase.request`)**: Supports comprehensive fields required for procurement—capturing requester, department, project, donor, award, output, activity, budget line, requested items (`lhi.purchase.request.line`), justification, required dates, emergency status, and more.
- **Validations & Thresholds**: 
  - Prevents PR submission if required dates fall outside the overarching project's active constraints (`_check_grant_dates`).
  - Automatically calculates estimated totals and assigns standard procurement methods (`direct` < $5K, `rfq` < $50K, `tender` >= $50K).
- **Approval Engine Interconnect**: Submitting a PR actively triggers the dynamic `lhi_approval_matrix` engine (by passing `document_type = 'purchase'`), finding the right matrix, segregating duties, and mapping the approval hierarchy dynamically.

### 2. Operational Commitments (`lhi_procurement_commitment`)
- **Procurement Commitment (`lhi.procurement.commitment`)**: Designed to lock/reserve a budget without posting an explicit financial/accounting entry initially.
- **Automated Lifecycle**: 
  - Extension on `lhi.purchase.request` (`_inherit`) automatically tracks its `lhi_approval_state` and triggers the creation of a Procurement Commitment referencing the exact PR value and codes as soon as it flips to `approved`.
  - When an approved PR is `cancelled`, the extension ensures the associated operational commitment automatically flips from `reserved` to `released`, effectively un-committing the budget.

## Security & Reliability
- **Multi-Company Rules**: Both models enforce `lhi_base` level `ir.rule` scoping to isolate requests and budget commitments by company boundary.
- **Segregation of Duties**: Delegated primarily to `lhi_approval_matrix`, but users cannot manually force the `commitment_id` generation or bypass PR approval checks.
- **Test Integrity**: Validated the automatic generation and release logic of operational commitments inside the automated test suites, proving the workflow hooks cleanly into `write()` overrides.
