# Sprint 22 Delivery Summary: Dormant Accounting Workstream

## Objectives Met
Successfully initiated the Dormant Accounting Workstream via the `lhi_accounting_base` module. This sprint focused on safely assessing the current accounting configuration and establishing robust, production-safe feature flags, explicitly preventing unauthorized financial posting prior to the official LHI Accounting Cutover.

## Models and Features

### 1. Server-Side Feature Gate (`lhi.accounting.feature.gate`)
- Developed a stringent, server-side validation module that intercepts financial transaction requests.
- **Posting Blockers**: Overrode `account.move` (`action_post`), `account.payment` (`action_post`), and `account.bank.statement` (`button_validate`). Unless the feature gate is explicitly activated via the configuration parameter `lhi_accounting_base.is_accounting_cutover_active`, any attempt to post journals, create vendor bills, record payments, or reconcile banks is automatically rejected with a `UserError`.

### 2. Sandbox Testing Environment
- **Menu Visibility Control**: The standard Odoo Invoicing and Accounting dashboards have been hidden from the general user base.
- **Dedicated Sandbox Group**: Created the `LHI Accounting Sandbox Tester` security group. Members of this group can view the Accounting menus in development/sandbox environments to configure the Chart of Accounts and Taxes. However, they are still strictly blocked by the server-side feature gate if they attempt to post transactions in an unauthorized environment.

### 3. Consultation and Assessment Documentation
- Delivered a structured markdown document (`docs/assessment.md`) mapping out the prerequisites for the accounting migration. 
- It covers the Chart of Accounts mapping, Journal/Tax design, Donor reporting requirements (tying `account.analytic.account` to Power BI datasets), and a checklist for the Migration Inventory (Vendor Bills, Outstanding Advances, Open Receivables).

## Security & Reliability
- **Fail-Closed Design**: The feature flag defaults to `False`. If the configuration parameter is missing or unset, Odoo treats it as securely disabled, preventing accidental financial corruption.
- **Automated Testing**: Created Python tests (`test_feature_gate.py`) to explicitly simulate an attempted journal post while the gate is closed. The tests verified that the `UserError` successfully halts the transaction, and verified that posting is allowed when the gate is simulated as open. The tests executed cleanly against the Odoo engine without errors.
