# Programs and Grants Hub Delivery

- Reuses `lhi.project`, `lhi.award`, `lhi.workplan.activity`, approval groups,
  departmental records, and SharePoint document metadata.
- Adds `lhi.project.budget`, `lhi.project.budget.line`,
  `lhi.activity.budget.allocation`, `lhi.activity.memo`,
  `lhi.execution.request`, and `lhi.payment.retirement`.
- Adds no accounting models, journal entries, production data, migrations,
  secrets, environment variables, or new external permissions.
- Project-funded execution is denied without an approved matching memo and
  budget line. Standalone departmental requests remain project-optional.
- Payment completion requires a manually entered Enterprise Odoo reference.
- Multi-company rules and least-privilege ACLs apply to new lifecycle models.
- Rollback requires the pre-deployment code and database backup plus queue and
  SharePoint metadata reconciliation; no webhook changes are introduced.

## Verification recorded on 2026-07-19

- `python3 -m compileall` passed for the four affected addons.
- All 26 affected XML files passed Python ElementTree well-formedness parsing.
- The 57-addon custom dependency graph has no cycles.
- All 65 relational fields introduced by the hub resolve to a core model or a
  model supplied by an explicit dependency.
- `git diff --check` passed.
- A database install was not executed in the development shell: the Coolify
  runtime configuration is not mounted, Docker access is unavailable, and the
  local Python environment lacks Odoo runtime dependency `passlib`. Deployment
  must remain blocked until the disposable-database install and non-superuser
  workflow/security tests pass in the Coolify runtime.

## Coolify installation and rollback

After a database backup, run the Odoo 19 binary inside the application
container with its mounted configuration and a newly created disposable
database. Install `lhi_programme_management,lhi_dashboard`, confirm exit code
zero, and run the affected Python test tags. Then update only
`lhi_meal,lhi_results_framework,lhi_programme_management,lhi_dashboard` on the
production database and restart the normal service. Do not use `-u all`.

Rollback consists of restoring the pre-deployment Git revision and the matching
database backup, then restarting Odoo. Reconcile any execution requests,
retirements, Enterprise payment references, and SharePoint metadata created
after the backup before restoring; there are no new queues or webhooks.

## Recovery validation recorded on 2026-07-20

- Replaced the invalid translated-label purchase-request view selector with
  the unique technical field anchor `activity_id`.
- Replaced positional Fleet, MEAL, and Asset locators with unique technical
  field anchors. The existing Media locator uses the stable page name `links`.
- Each of the six parent anchors matched exactly one node in its inspected
  source architecture; no related `@string` or positional XPath remains.
- Restored dashboard assets to `web.assets_backend`, which the inspected Odoo
  19 `web` manifest includes in the active `web.assets_web` webclient bundle.
- Confirmed one dashboard action registration, matching XML tag and template,
  and 14 existing dashboard backend asset paths.
- Parsed 38 affected XML files successfully, compiled all affected Python
  packages, confirmed an acyclic dependency graph, and resolved Media grant
  relations to canonical `lhi.award` through `lhi_base`.
- `xmllint`, the production Odoo runtime/configuration, database access,
  Coolify metadata, and Docker access are unavailable in this shell. Therefore
  disposable and production module operations and browser validation remain
  mandatory deployment gates and are not reported as passed.
