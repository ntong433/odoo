# LHI application RBAC delivery summary

Date: 2026-08-01
Target: Odoo 19 Community
Canonical production URL: `https://work.lhinigeria.org`

## 1. Root-cause report

The repository used several independent authorization models: hard-coded
dashboard group lists, Entra-synchronized department codes, legacy sidebar
mappings, native menu groups and broad model ACLs. Operations and Funding roots
used `base.group_user`; empty widget groups meant public; application roles
shared one Odoo privilege; and direct actions/dashboard RPCs had no common
application check. Odoo's additive permissions then made the leaks cumulative.

The detailed pre-change evidence is in
`rbac_preimplementation_audit.md`.

## 2. Current permission matrix (before refactor)

| Role | Dashboard/sidebar | Launcher/menu | Direct action/RPC | Main-model access |
|---|---|---|---|---|
| Ordinary internal user | Operations/Funding and empty widgets could appear | Operations/Funding and several roots leaked | Paths disagreed; some RPCs lacked an app check | Broad `base.group_user` ACLs granted read or CRUD |
| Warehouse Officer | Operations inferred from Store/department paths | HUB, Inventory and Operations paths were mixed | One path denied while another could load | HUB and stock access mixed with Operations roles |
| Programme role | Programs plus unrelated Operations/HUB paths | Programme roles occurred on HUB/Operations menus | No shared action gate | Several lifecycle ACLs used Internal User |
| Manager/system user | Dashboard hard-coded special cases | Menu visibility depended on unrelated groups | Protected menu bypass did not guarantee model rights | Generic manager/system ACLs crossed app boundaries |

## 3. Final permission matrix

| Role | Dashboard | Sidebar | Launcher/root | Direct action | Main ACL |
|---|---|---|---|---|---|
| No Access | Hidden | Hidden | Hidden | `AccessError` | No positive application ACL; shared-engine exceptions below |
| Viewer | Visible | Visible | Visible | Allowed | Scoped read only |
| Officer/User | Visible | Visible | Visible | Allowed | Scoped operational rights, normally no delete |
| Manager | Visible | Visible | Visible | Allowed | Intended management/configuration rights |
| ERP Administrator | Every installed app | Every installed app | Every installed app | Allowed | All application manager capabilities |

Memo is the intentional employee exception. Approval workflow participants keep
the minimum shared-engine ACLs needed to submit/act on their own requests; this
does not grant Approvals navigation or configuration. Signature Administration
is manager-only because it exposes provider/webhook diagnostics.

## 4. Files changed

No Odoo core file was modified. Changes are confined to `custom-addons/`:

- Central implementation: `lhi_security/models/res_users.py`,
  `ir_actions.py`, `ir_ui_menu.py`, security XML/CSV, manifest, migrations,
  tests and these docs.
- Navigation implementation: `lhi_dashboard` models/data/views/tests/migration
  and `lhi_web_shell` sidebar plus JS test.
- Application RPCs and security: `lhi_asset_management`,
  `lhi_hub_management`, `lhi_inventory`, `lhi_leave_bridge`.
- Application menus, manifests, ACLs and rules: `lhi_approval_matrix`,
  `lhi_donor_management`, `lhi_fleet_operations`,
  `lhi_funding_opportunity`, `lhi_meal`, `lhi_media_communications`,
  `lhi_memo_management`, `lhi_partner_management`, `lhi_powerbi`,
  `lhi_procurement`, `lhi_procurement_commitment`,
  `lhi_programme_management`, `lhi_project_amendment`,
  `lhi_project_closeout`, `lhi_project_compliance`, `lhi_project_issue`,
  `lhi_project_reporting`, `lhi_project_risk`, `lhi_project_workplan`,
  `lhi_proposal_budget`, `lhi_proposal_management`, `lhi_purchase_order`,
  `lhi_purchase_request`, `lhi_reporting_hub`, `lhi_results_framework`,
  `lhi_signature_bridge` and `lhi_vendor_management`.
- Cross-application regression coverage: `lhi_integrated_tests` manifest and
  `tests/test_rbac_security.py`.

Use `git show --stat --name-only <delivery-commit>` for the exact file list.

## 5. New groups created

New positive groups are: Operations Viewer; HUB Manager; Asset Viewer;
Procurement Viewer; Inventory Viewer and Manager; Fleet Viewer and Manager;
Programs and Grants Viewer; Approvals Viewer and Manager; Reports Viewer,
Officer and Manager; Power BI Viewer, Officer and Manager; MEAL Viewer and
Manager; HR and Leave Viewer and Manager.

Twelve dedicated Odoo 19 `res.groups.privilege` records expose independent
native selections with the placeholder **No Access**. No negative group was
created.

## 6. Existing groups reused

Reused operational roles include Operations Officer/Manager, Warehouse Officer,
Asset Officer/Manager, Procurement Officer/Manager, Store Officer, Fleet
Officer, Project Officer/Manager, Programme User/Approver/Director, Executive
Approver, MEAL Officer, HR Officer, the existing Media hierarchy, LHI Employee,
Memo roles and Signature Preparation/Administrator roles.

## 7. Group inheritance changes

- Each standard Manager now implies Officer/User, which implies Viewer.
- Warehouse Officer implies HUB Viewer and Store Officer, not Operations.
- Operations roles no longer imply HUB, Warehouse or native Stock roles.
- Programme, Procurement, Store, Fleet, MEAL and Media roles no longer imply
  the retired duplicate Programs Viewer.
- The legacy Programs Viewer is a compatibility alias to the canonical Viewer.
- ERP Administrator implies all central and installed optional app managers.
- A static cycle scan found zero cycles across 72 custom groups and 113 positive
  implied edges.

## 8. Root menu changes

Positive root entitlements and stable `lhi_app_key` values now protect
Operations, HUB, Assets, Procurement, Inventory, Fleet, Programs and Grants,
Approvals, Reports, Power BI, Media, MEAL, Memo, Signature Administration and
HR/Leave. Independently assignable applications are top-level roots; duplicate
Operations and opportunity entry points were disabled or nested under their
canonical root. Restricted roots no longer use `base.group_user`.

## 9. Dashboard changes

`LHI_APP_ACCESS_GROUPS` drives the application definitions. Restricted cards
are returned only after both central entitlement and native menu visibility
succeed. Department codes and specialized group lists no longer authorize an
app. `app_key` and `is_public_internal` are mutually exclusive access modes;
an empty group list now fails closed. Six maintained utility widgets are
explicitly internal-public.

## 10. Sidebar changes

Sidebar entries consume the same server-authorized application payload.
`lhi.sidebar.role.mapping.app_key` is mandatory on active mappings. The legacy
group field is retained only for migration history and cannot grant access.

## 11. Launcher changes

The native launcher is controlled by tagged root menus and the centralized
`ir.ui.menu._visible_menu_ids()` filter. Denied tagged roots and their
descendants fail closed. The protected administrator behavior is preserved,
then filtered through the explicit ERP Administrator bypass.

## 12. Server-side access checks

- `res.users.has_lhi_app_access`, `check_lhi_app_access` and the RPC-safe
  `get_lhi_allowed_apps` validate known keys and never use `sudo()` for the
  ordinary authorization decision.
- `ir.actions.actions._get_action_dict()` resolves an explicit action key or a
  tagged menu ancestor and denies unauthorized direct action loads.
- Operations, HUB and Asset dashboard RPCs validate their application before
  reading record-rule-scoped data.
- Leave synchronization and local approval/rejection methods validate HR/Leave
  or Approvals access.
- Dashboard approvals, quick actions and global search validate the relevant
  app and model ACL before returning data.

## 13. ACL and record-rule changes

Viewer read ACLs, Officer operational ACLs and Manager ACLs replace generic
Internal User, ERP Manager or System grants across the affected app families.
Foundational Programs ACLs and selected Odoo stock ACLs are reassigned from
generic Internal User to their positive Viewer role. HUB Viewer retains the
read-only stock ACLs required by its overview. Existing company, HUB, office,
department, project, custody and participant domains remain in force. Changed
`noupdate` rules are repaired to the canonical Viewer group by migration.

Intentional shared-workflow exceptions are documented in
`rbac_administration.md`; they do not authorize an application surface.

## 14. Migration implementation

- `lhi_security/migrations/19.0.2.0.0/post-migrate.py` repairs role chains,
  removes obsolete implied edges, preserves legitimate direct legacy Programs
  Viewer memberships, assigns optional managers to ERP Administrator, repairs
  foundational ACLs and rewrites exact changed `noupdate` rules.
- `lhi_dashboard/migrations/19.0.2.0.0/post-migrate.py` explicitly classifies
  utility widgets, infers known legacy mapping keys and deactivates unknown
  active mappings fail closed.
- `lhi_inventory/migrations/19.0.2.0.0/post-migrate.py` repairs exact stock ACLs
  even if their original XML IDs are `noupdate`.

All migrations use bounded exact XML-ID lists, savepoints where records are
handled independently, idempotent comparisons and credential-free logging.

## 15. Test files added or changed

- Added `lhi_security/tests/test_application_access.py`.
- Changed `lhi_security/tests/test_security_rules.py`.
- Changed `lhi_dashboard/tests/test_dashboard.py`.
- Changed HUB common/security tests.
- Replaced the stale integrated RBAC test with real role, menu, dashboard,
  action, ACL, cache and James Bassey regression coverage.
- Changed `lhi_web_shell/static/tests/lhi_navigation_tests.js`.

The integrated matrix covers all 13 standard restricted applications plus the
Memo and Signature Administration exceptions. It uses non-superuser identities
for authorization assertions.

## 16. Test commands executed

Executed in this workspace:

```bash
.venv/bin/ruff check <changed RBAC Python files> --output-format concise
.venv/bin/python -m compileall -q <changed Python and migration files>
node --input-type=module --check < changed-sidebar.js
node --input-type=module --check < changed-navigation-test.js
.venv/bin/python <XML RelaxNG, manifest, dependency and ACL-CSV validator>
.venv/bin/python <changed XML external-ID validator>
.venv/bin/python <custom implied-group cycle validator>
.venv/bin/python odoo/odoo-bin cloc -p custom-addons/lhi_security \
  -p custom-addons/lhi_dashboard -p custom-addons/lhi_inventory --verbose
git diff --check
```

Database connectivity and container availability were also checked with
`psycopg2`, `docker compose config --services` and the Docker client.

## 17. Test results

Passed:

- Ruff on all new and materially changed RBAC Python files.
- Python compilation, including all three migrations.
- JavaScript syntax for both changed JS files.
- Odoo RelaxNG validation for 64 changed XML files.
- Literal/dependency/data-file validation for 34 changed manifests.
- Shape validation for 28 changed ACL CSV files.
- Resolution scan for 803 changed-XML external references.
- Custom group graph scan: 72 groups, 113 positive edges, no cycle.
- Odoo `cloc` path loading and `git diff --check`.

Not executed: Odoo registry installation/upgrades, Python test tags, browser
asset compilation and manual browser scenarios. There is no PostgreSQL server
or socket in the workspace; TCP port 5432 refuses connections; Docker access is
denied to this user; and Compose cannot resolve the absent secret environment
values. These checks must pass on the designated test database before
production approval. No database test is reported as passed.

## 18. Module upgrade commands

On a cloned test database with secrets supplied by the approved environment:

```bash
export LHI_TEST_DB='<test-database-name>'
.venv/bin/python odoo/odoo-bin \
  --addons-path=odoo/addons,custom-addons \
  -d "$LHI_TEST_DB" --stop-after-init \
  -u lhi_security,lhi_dashboard,lhi_web_shell,lhi_approval_matrix,lhi_asset_management,lhi_hub_management,lhi_inventory,lhi_fleet_operations,lhi_funding_opportunity,lhi_donor_management,lhi_programme_management,lhi_proposal_management,lhi_proposal_budget,lhi_project_workplan,lhi_project_risk,lhi_project_issue,lhi_project_reporting,lhi_project_compliance,lhi_project_amendment,lhi_project_closeout,lhi_results_framework,lhi_meal,lhi_partner_management,lhi_procurement,lhi_procurement_commitment,lhi_purchase_request,lhi_purchase_order,lhi_vendor_management,lhi_reporting_hub,lhi_powerbi,lhi_media_communications,lhi_memo_management,lhi_signature_bridge,lhi_leave_bridge,lhi_integrated_tests
```

Then run targeted tests:

```bash
.venv/bin/python odoo/odoo-bin \
  --addons-path=odoo/addons,custom-addons \
  -d "$LHI_TEST_DB" --stop-after-init --test-enable \
  --test-tags /lhi_security,/lhi_dashboard,/lhi_hub_management,/lhi_integrated_tests:TestIntegratedApplicationRBAC
```

Use a disposable database or an approved clone; never run test tags against
production.

## 19. Deployment steps

1. Obtain RBAC/security owner approval of test evidence and the user-role delta.
2. Back up the production database and persistent volumes in Coolify.
3. Build/deploy the image containing the delivery commit; do not patch a running
   container.
4. Supply existing secrets through Coolify/approved secret storage. No new
   secret is introduced by this change.
5. Run the changed-module upgrade as a one-off task, then restart Odoo workers.
6. Verify `https://work.lhinigeria.org`, protected local administrator access,
   James/employee/viewer/manager scenarios and multi-company/HUB scope.
7. Review migration logs and any deactivated unknown sidebar mappings.

The Accounting feature flag is unchanged and must remain disabled.

## 20. Rollback steps

1. Stop user writes and capture logs/evidence.
2. Redeploy the previous known-good commit/image.
3. Restore the pre-upgrade database backup. Code rollback alone is insufficient
   because group relations, ACL/rule assignments and new fields are persistent.
4. Restore the matching persistent volume snapshot if the deployment process
   changed it, then restart workers and clear normal web sessions/caches.
5. Verify protected admin recovery and the previous role/navigation behavior.

No queue payload, webhook registration, Entra state, Graph state, SharePoint
item, OpenSign envelope or integration credential is changed by this delivery;
do not replay or delete any of them during rollback.

## 21. Known warnings not caused by this change

- A repository-wide Ruff run reports legacy `__init__` import-style warnings,
  unused imports and several pre-existing test locals outside the focused RBAC
  files.
- A plain Node runtime cannot resolve Odoo's browser-only `@web/*` aliases;
  syntax was validated through module-mode stdin, while full asset compilation
  remains a database/runtime check.
- Database/registry warnings are unknown until the deferred upgrade runs; none
  are claimed absent.

## 22. Git diff summary

The final staged candidate contains 152 custom-addon files with 2,827
insertions and 570 deletions. The commit-level summary is produced with:

```bash
git show --stat --oneline --decorate --no-renames <delivery-commit>
```

No `odoo/` core or submodule file is part of the delivery.

## 23. Final Git commit hash

The immutable hash is recorded in the delivery response after creating the
requested commit:

```text
refactor(security): unify module RBAC and navigation visibility
```

## Required project configuration disclosures

- New/changed environment variables or secret-store entries: none.
- Entra ID or Microsoft Graph permissions: none.
- SharePoint tenant/site/library/content-type/permission/webhook/retention
  changes: none.
- Business-document storage architecture: unchanged; SharePoint remains the
  system of record for document bytes.
- Database schema: adds `lhi_app_key` to actions and menus; adds `app_key` and
  `is_public_internal` to dashboard widgets; adds `app_key` to sidebar mappings.
- Pre-migration check: database backup, installed-module inventory, direct-role
  export, unknown active sidebar mapping report and James-equivalent user list.
- Post-migration check: role graph, all 15 launcher roots, deactivated mappings,
  ACL/rule XML IDs, ERP Administrator implications and scoped dashboard counts.
- Manual evidence: not captured in this environment; owner is the deployment
  lead, required before production approval, with confidential data redacted.
- Remaining risk: database upgrade/assets/tests are deferred because the local
  runtime is unavailable. Mitigation is the cloned-database gate above; owners
  are the Odoo technical lead and LHI security owner; approval is required from
  both before production deployment.
