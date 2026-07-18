# Dashboard, application menu, branding and icon redesign

Date: 2026-07-18

## Authorization design

`lhi.dashboard.widget.get_accessible_apps()` resolves real menus by XML ID,
requires the menu to be present in Odoo 19's `_visible_menu_ids()`, checks any
target action groups, and then applies LHI functional-group/department-code
eligibility. It does not use `sudo()`, labels, generated routes, or database IDs.

Mappings:

- Pipeline: project officer/manager/programme director; `PIPELINE`, `PROGRAMME(S)`.
- Procurement: procurement officer/manager; `PROCUREMENT`.
- Operations: supervisor/manager; `OPERATIONS`.
- Assets: store officer; `ASSET(S)`, `OPERATIONS`.
- Accounting: finance reviewer/accounting sandbox; `ACCOUNTING`, `FINANCE`.
- MEAL: MEAL officer/sensitive-data group; `MEAL`.
- Inventory: store officer; `INVENTORY`, `STORE`.
- Fleet: fleet officer; `FLEET`, `OPERATIONS`.
- Approvals: executive approver/manager; `APPROVALS`.
- Projects & Grants: project roles; `PROJECTS`, `GRANTS`, `PROGRAMME(S)`.
- HR: HR officer; `HR`, `HUMAN_RESOURCES`.
- Signatures: procurement roles; `LEGAL`, `PROCUREMENT`.
- Settings: `base.group_system` only.

The core Odoo 19 ACL for `ir.module.module` was verified at pinned commit
`4bd64dafecdb4d02e998379bbeac2825f483e5d9`: only `base.group_system` has CRUD.
The Apps menus and main Apps action now explicitly carry that same group.

## Verification performed

- Python compilation: passed.
- Eight changed manifests parsed: passed.
- Eight changed XML/QWeb files parsed: passed.
- Custom dependency graph (55 modules): acyclic.
- All 19 required local SVGs present and non-empty: passed.
- Every `web_icon` module/path reference resolves locally: passed.
- Responsive grid/focus static assertions: passed.
- `git diff --check`: passed.

Odoo database tests, browser light/dark tests, HTTP status checks and deployment
were not run because this workstation has neither an initialized Odoo source
checkout nor Docker socket access. These must not be reported as passed.

## Deployment

Upgrade only:

`lhi_web_shell,lhi_dashboard,lhi_funding_opportunity,lhi_purchase_request,lhi_asset_management,lhi_leave_bridge,lhi_powerbi,lhi_reporting_hub`

Use the deployment's actual `odoo-bin`, configuration and database paths with
`--stop-after-init --no-http`, restore the normal Coolify command, restart once,
then test `?debug=assets` followed by minified assets in Incognito.

## Rollback

Revert the delivery commit, redeploy the preceding image/revision, upgrade the
same module list once, restore the normal Coolify startup command, and restart.
No model fields, database tables, external permissions, secrets, queues,
webhooks or SharePoint/Entra configuration are changed by this delivery.
