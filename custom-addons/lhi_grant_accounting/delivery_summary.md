# Sprint 23 Delivery Summary: NGO Sandbox Modules

## Objectives Met
Successfully delivered the core components for the NGO Accounting Sandbox, consisting of 6 distinct but interrelated modules. All components strictly adhere to the Dormant Accounting framework, ensuring no live financial impact occurs prior to formal migration approval.

## Delivered Modules

### 1. Grant Accounting (`lhi_grant_accounting`)
- Extended `account.analytic.account` to support standard NGO tracking dimensions: Donor, Award, Project, Output, Activity, Funding Source, Cost Centre, and Location.
- Added explicit donor restrictions (Unrestricted, Temporarily Restricted, Permanently Restricted) and implemented a validation rule ensuring restricted funds must be linked to a Donor.

### 2. Budget Control (`lhi_budget_control`)
- Introduced the `lhi.budget` and `lhi.budget.line` models to map planned expenditure against the new analytic dimensions.
- Budget lines automatically compute the `available_amount` as `planned_amount - commitment_amount - actual_amount`.
- Future integration points are stubbed in the overridden `account.move.line` to intercept budget exhaustion based on the LHI Feature Gate.

### 3. Multi Currency (`lhi_multi_currency`)
- Extended `account.move` to preserve Donor-specific exchange information (e.g., Donor Rate, Date, Source). This enables LHI to report back to international donors in their required currency regardless of Odoo's base accounting currency.

### 4. Withholding Tax (`lhi_withholding_tax`)
- Developed a standalone `lhi.wht.certificate` model to manage the lifecycle of deductions, capturing approval, remittance (to FIRS/SIRS), and delivery status of the certificate to the respective Vendor.

### 5. Advance Accounting (`lhi_advance_accounting`)
- Implemented `lhi.staff.advance` to manage requested funds by employees.
- Security hooks guarantee that "Payment" or "Retirement" entries will fail immediately via a `UserError` if the Accounting Cutover feature gate is disabled.

### 6. Field Cashbooks (`lhi_field_cash`)
- Introduced `lhi.field.cashbook` allowing Custodians to manage remote field office balances. Includes a locked reconciliation workflow to enforce proper counting and discrepancy reporting.

## Security & Reliability
- **Isolated Testing Environment**: All models have dedicated base tests.
- **Fail-Closed Integration**: Functions that trigger underlying `account.move` creation (like Staff Advances) strictly call `check_accounting_enabled()`, guaranteeing that these tools can be configured and demonstrated safely in the sandbox.
- **Successful Execution**: The automated Docker tests for all 6 modules successfully passed against the Odoo engine.
