# Odoo Enterprise Accounting Configuration Assessment

## 1. Current State
- **Odoo Version**: Odoo 19 Enterprise (via `account` module)
- **Status**: Currently deactivated for production business use. LHI is relying on a legacy Enterprise Accounting system until cutover.

## 2. Chart of Accounts (CoA) Mapping
- **Action Required**: The legacy CoA needs to be extracted, cleansed, and mapped to Odoo's `account.account` structure.
- **Consultation Question**: Do we need to retain all historical legacy accounts, or will we map legacy history into consolidated opening balances within Odoo?

## 3. Journals and Taxes
- **Journals**: Need to configure specific journals for Donor Funds, Operational Expenses, Payroll, and Bank/Cash reconciliations.
- **Taxes**: Ensure Nigerian withholding tax (WHT) and VAT configurations are verified against `account.tax`.

## 4. Donor Reporting Requirements
- **Challenge**: Odoo’s native analytical accounting (`account.analytic.account`) must be configured to map to Donor Grants and Projects so that `account.move.line` items can be sliced by Donor in Power BI.

## 5. Migration Inventory
- Open Vendor Bills (AP)
- Outstanding Advances / Staff Retirements
- Open Customer Invoices (AR)
- Bank Account Reconciliation balances
- Fixed Asset net book values

## 6. Cutover Controls (Implemented)
- **Feature Flag**: A system parameter `lhi_accounting_base.is_accounting_cutover_active` strictly blocks `account.move` and `account.payment` posting unless explicitly turned on.
- **Sandbox Testing**: Users placed in the `LHI Accounting Sandbox Tester` group can see the menus in non-production environments to validate the CoA and Journals, but the server-side gate prevents any real financial consequence if mistakenly deployed to production before cutover.
