# LHI application RBAC administration

## Purpose and authority

Odoo RBAC is the authorization authority. Microsoft Entra ID may synchronize
identity attributes and explicitly configured functional memberships, but it
must not decide application access independently of these Odoo groups.

The authoritative application registry is
`lhi_security.models.res_users.LHI_APP_ACCESS_GROUPS`. Dashboard cards, the
sidebar, launcher menus, root menus and direct action loading all use the same
application key. Model ACLs and record rules remain the data boundary.

## Assigning application access

Open **Settings > Users & Companies > Users**, select the user, and choose one
level under each LHI application privilege. Each privilege displays **No
Access** when no positive group is selected. No negative group exists.

The standard hierarchy is:

| UI level | Effective capability |
|---|---|
| No Access | No positive application group; app navigation and direct actions are denied |
| Viewer | Application visibility and scoped read access |
| Officer/User | Viewer plus the application's operational permissions |
| Manager | Officer/User plus approved management/configuration permissions |

Changing Manager to Viewer or No Access uses Odoo 19's native privilege
selection and removes the higher direct selection without changing unrelated
application roles.

## Application role map

| Application key | Viewer/access | Officer/user | Manager |
|---|---|---|---|
| `operations` | Operations Viewer | Operations Officer | Operations Manager |
| `hub` | HUB Viewer | Warehouse Officer | HUB Manager |
| `assets` | Asset Viewer | Asset Officer | Asset Manager |
| `procurement` | Procurement Viewer | Procurement Officer | Procurement Manager |
| `inventory` | Inventory Viewer | Store Officer | Inventory Manager |
| `fleet` | Fleet Viewer | Fleet Officer | Fleet Manager |
| `programs_grants` | Programs and Grants Viewer | Project Officer / Programme User | Project Manager / Programme Approver |
| `approvals` | Approvals Viewer | Executive Approver | Approvals Manager |
| `reports` | Reports Viewer | Reports Officer | Reports Manager |
| `power_bi` | Power BI Viewer | Power BI Officer | Power BI Manager |
| `media` | Media Viewer | Media Requester/Officer/Reviewer | Media Manager |
| `meal` | MEAL Viewer | MEAL Officer | MEAL Manager |
| `memo` | LHI Employee | Memo workflow roles | Memo Administrator |
| `signatures` | Not exposed as a general viewer app | Preparation occurs in business documents | Signature Administrator |
| `hr_leave` | HR and Leave Viewer | HR Officer | HR and Leave Manager |

## Intentional inheritance

- Manager implies Officer/User, which implies Viewer.
- Warehouse Officer implies HUB Viewer and Store Officer. This grants the
  governed HUB workspace and the Inventory functions needed for warehouse
  work. It does not imply Operations Viewer.
- Programs roles imply Programs and Grants Viewer. They do not imply
  Operations or HUB application access.
- ERP Administrator implies every installed application manager, including
  Media, Memo and Signature Administration. It does not expose stored secrets
  in the browser.
- Viewer roles imply the internal employee baseline where needed; the reverse
  is never true. An employee therefore receives no restricted Viewer group.

## Exceptions and shared engines

- Memo is intentionally available to every internal LHI employee. Memo
  administration remains restricted.
- Approval requests, route matrices and their scoped participant records are a
  shared workflow engine used by Memo, Procurement, HUB and other applications.
  Employees retain the minimum existing engine ACLs needed to submit and act on
  their own workflows. This does not grant the Approvals app, configuration
  menus or direct Approvals actions.
- Programme roles retain scoped HUB-request ACLs so programmes can request
  stock through their business workflow. They do not receive the HUB launcher
  or dashboard.
- Signature Preparation Officers work through source business documents. The
  standalone Signature Administration app is limited to Signature
  Administrators because it contains provider, webhook and diagnostic data.

## Role-change verification

After saving a role change:

1. Start a fresh user session or reload the web client.
2. Confirm the app agrees across My Apps, sidebar, launcher and root menu.
3. Open the app and verify the expected read/operational level.
4. For a removed role, verify that a saved direct action URL raises an access
   error.
5. For multi-company, HUB, office, department or project roles, verify both an
   allowed record and a record outside the user's scope.

Odoo cache invalidation on group and menu writes refreshes normal visible-menu
results. Do not patch browser storage or assign generic Internal User access to
work around a missing app.

## Upgrade procedure

Run the changed-module upgrade on a cloned database before production. The
post-migrations are idempotent and:

- repair positive role chains and remove only obsolete implied edges;
- translate direct memberships in the retired Programs Viewer alias to the
  canonical Viewer;
- repair foundational Programs ACLs and changed `noupdate` record rules;
- repair stock ACLs that previously granted generic Internal User access;
- classify maintained dashboard utilities explicitly and migrate/deactivate
  legacy sidebar mappings fail closed; and
- add every installed application manager to ERP Administrator.

Review users who historically depended on accidental cross-application
inheritance. Assign a positive application role only after the business owner
confirms the need.

## Security administration cautions

- Do not assign `base.group_system`, `base.group_user`, LHI Employee or a
  department merely to expose a restricted app.
- Do not add Viewer groups to a generic or default group.
- Preserve local protected administrator accounts for recovery.
- Do not add Entra, Graph, SharePoint or OpenSign secrets to groups, XML, logs
  or screenshots.
- Use a non-superuser account when testing ACLs and record rules.
