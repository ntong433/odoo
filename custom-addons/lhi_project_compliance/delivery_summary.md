# Sprint 10: Award Setup, Compliance, and Reporting Calendar Delivery Summary

## Objective
Operationalize an awarded grant and ensure robust compliance and setup.

## Deliverables
- **Grant Award Enhancement**: Developed `lhi_grant_award` to extend the core `lhi.award` model. Appended critical tracking metadata including Donor relationship mapping, signed agreement storage, closeout period tracking, reporting currency definitions, and extensive text blocks for compliance policies (indirect cost rules, procurement thresholds, reporting/audit requirements, branding, safeguarding, data protection, asset ownership, and record retention).
- **Project Compliance & Activation**: Implemented `lhi_project_compliance` extending `lhi.project`. Introduced a mandatory "Setup & Activation" state.
- **Project Activation Checklist**: Hardened the project lifecycle with a rigid 10-point checklist ensuring no project becomes `Active` until signed agreements, approved budgets, workplans, procurement plans, risk registers, MEAL setups, reporting calendars, and critical focal persons (PM, Finance, MEAL) are officially documented and approved.
- **Reporting Calendar Engine**: Built `lhi.reporting.calendar` to construct the schedule of compliance obligations mapped to a project/award. Tracks financial, narrative, audit, and MEAL reporting frequencies against strict due dates.
- **Automated Compliance Alerts**: Engineered cron jobs (`_cron_upcoming_deadlines`, `_cron_check_overdue_reports`) that monitor the reporting calendar daily. Automatically triggers Odoo To-Do activities 14 days before a deadline and escalates to a Warning activity when a report officially transitions to "Overdue/Late".

## Security Controls Enforced
- Expanded multi-company record rules (`ir.rule`) across the new reporting calendar to ensure company isolation for compliance obligations.
- All new UI fields, buttons, and state transitions respect standard Odoo 19 access mechanics, gating activation privileges to authorized Project Managers and ERP Admins without relying on deprecated frontend rules.

## Automated Verification
Executed Python unit tests verifying operational constraints:
- `test_activation_blocked`: Verifies that a `lhi.project` strictly blocks the `action_activate_project` trigger and raises a `ValidationError` if any checklist item is unchecked.
- `test_activation_success`: Verifies that once all criteria are met and focal points assigned, the system seamlessly activates the project and transitions the record state.
- `test_award_extension`: Validates the linkage of new extension fields (donor references, closeout periods) on the base `lhi.award` structure.

Installation, upgrade, and runtime tests complete without regression.
