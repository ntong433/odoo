# Sprint 9: Proposal Budget, Submission, and Award Conversion Delivery Summary

## Objective
Build proposal budgeting and convert successful proposals into awards and projects.

## Deliverables
- **Proposal Budget Model**: Created `lhi.proposal.budget` to manage multi-currency budgets for a proposal workspace.
- **Granular Budget Lines**: Implemented `lhi.proposal.budget.line` capturing donor category, LHI category, coding parameters (output, activity, location, department, cost centre), and calculation metrics (unit, unit cost, quantity, frequency, duration, exchange rate).
- **Cost-Share Tracking**: Added strict percentage-based distribution (Donor %, LHI %, Partner %) to each budget line, enforcing a constraint that the sum must exactly equal 100%. Computed fields automatically project total line amounts into the respective base currency contribution buckets.
- **Constraints & Validations**: Implemented database-level constraints to block duplicate budget lines, ensure percentage accuracy, and enforce that total requested donor funding does not exceed the opportunity funding ceiling.
- **Immutable Submissions**: Created `lhi.proposal.submission` to snapshot final documents (narrative PDF, budget Excel/PDF, annexes) marking the exact package submitted to the donor. Includes submission method tracking (Portal, Email, Physical) and acknowledgement tracking.
- **Clarification & Revision Tracking**: Built `lhi.proposal.clarification` to log donor feedback, deadlines, and internal responses tied back to specific submission records. 
- **Controlled Award Conversion**: Developed a transient wizard (`lhi.proposal.award.wizard`) that orchestrates the handover from a successful proposal submission into a live Grant/Award (`lhi.award`) and internal Implementation Project (`lhi.project`), preserving traceability back to the origin workspace.

## Security Controls Enforced
- Applied `base.group_erp_manager` restrictions to system-wide configuration elements.
- Applied `company_ids` level multi-company record isolation (`ir.rule`) on both budget and submission records to silo visibility across the enterprise.

## Automated Verification
Executed Python unit tests verifying computational logic:
- `test_budget_calculations`: Validates that the formula `(unit_cost * quantity * frequency * duration * exchange_rate)` correctly distributes against the Donor/LHI/Partner percentage splits.
- `test_budget_percentage_validation`: Asserts that an exception is raised if contribution splits do not equal exactly 100%.
- `test_budget_ceiling_validation`: Asserts that if the budget lines exceed the Opportunity's `funding_ceiling`, the system prevents the operation.

Installation, upgrade, and runtime tests complete without regression.
