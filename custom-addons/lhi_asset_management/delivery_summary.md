# LHI Asset Register — 19.0.2.0.0 Delivery Summary

## Scope and architecture

This release upgrades the existing `lhi_asset_management` addon in place. It
does not create a duplicate asset model and does not modify Odoo core. The
register is operational: it does not depend on or create Accounting, HR,
Employees, Sales, Rental, stock valuation, invoices, payments, journal entries,
or `hr.employee` records.

Existing models retained:

- `lhi.asset`
- `lhi.asset.category`
- `lhi.asset.transfer`
- `lhi.location`
- `res.users`, `lhi.project`, `lhi.programme`, `lhi.award`,
  `lhi.funding.source`, `lhi.office`
- `stock.warehouse` for the optional current HUB link
- `lhi.approval.matrix` and `lhi.approval.request`
- `lhi.document.item` and the existing SharePoint storage service

New models:

- `lhi.asset.condition`
- `lhi.asset.history`
- `lhi.asset.tag.rule`
- `lhi.asset.tag.counter`
- `lhi.asset.retag.request`
- `lhi.asset.import.wizard`
- `lhi.asset.import.batch`
- `lhi.asset.import.row`

## Delivered behavior

- Complete operational asset identity, ownership, funding, project/programme,
  location, current HUB, condition, value, warranty, restriction, document, and
  lifecycle fields.
- Configurable tag convention
  `LHI/{OWNER_OR_PROJECT}/{ORIGIN_STATE}/{CATEGORY}/{SEQUENCE}`.
- Configurable global, owner/project, or full-prefix sequence scope.
- A parameterized PostgreSQL UPSERT allocates sequence numbers atomically; a
  unique database constraint protects the final tag.
- Tags are immutable after confirmation. Re-tagging requires a separate request,
  a reason, an Asset Manager other than the requester, central audit logging,
  and preservation of the previous tag.
- Legacy asset numbers remain unchanged and are classified as valid-convention
  or non-standard legacy tags.
- Configurable conditions seeded with New, Good, Fair, Damaged, Under Repair,
  and Unserviceable.
- Immutable history for custody, state, office, HUB, location, condition,
  status, project, owner, funding source, tag, transfer, loss, and disposal.
- Transfer and disposal workflows use the reusable approval-matrix engine.
- Permission-aware Asset Register overview cards and drill-down analyses.
- Barcode and QR labels plus register, condition, handover, transfer, and
  disposal reports.
- CSV/XLSX import preview supporting the exact legacy headers, including
  `Purchase Vaue` and `cat_cal`; source and error files are verified in
  SharePoint.
- Import row correction, validation, duplicate detection, partial imports,
  reconciliation, error reports, and controlled rollback before downstream
  asset transactions.
- Dedicated Asset Officer, Asset Manager, and System Auditor access. Generic
  internal users no longer receive asset write access.

## Changed files

- `__manifest__.py`
- `models/__init__.py`
- `models/lhi_asset.py`
- `models/lhi_asset_tag.py`
- `models/lhi_asset_retag.py`
- `models/lhi_asset_transfer.py`
- `models/lhi_asset_import.py`
- `models/approval_matrix.py`
- `models/res_country_state.py`
- `security/ir.model.access.csv`
- `security/lhi_asset_security.xml`
- `data/ir_sequence_data.xml`
- `data/lhi_asset_configuration_data.xml`
- `views/lhi_asset_views.xml`
- `views/lhi_asset_transfer_views.xml`
- `views/lhi_asset_retag_views.xml`
- `views/lhi_asset_import_views.xml`
- `views/lhi_asset_configuration_views.xml`
- `views/menu_views.xml`
- `static/src/js/asset_dashboard.js`
- `static/src/xml/asset_dashboard.xml`
- `static/src/scss/asset_dashboard.scss`
- `report/lhi_asset_reports.xml`
- `report/lhi_asset_report_templates.xml`
- `migrations/19.0.2.0.0/pre-migrate.py`
- `migrations/19.0.2.0.0/post-migrate.py`
- `tests/test_asset.py`
- `docs/administrator_guide.md`
- `docs/user_guide.md`
- `docs/migration_and_rollback.md`

Related compatibility changes:

- `lhi_security/security/security_groups.xml`
- `lhi_security/__manifest__.py`
- `lhi_programme_asset_bridge/models/asset_programme_extension.py`
- `lhi_programme_asset_bridge/__manifest__.py`

## Schema and migration

The release adds the fields and models listed above. The pre-migration:

- stops on duplicate issued tags;
- stops on duplicate serial numbers within a company;
- stops on missing or unsafe category codes;
- converts old technical tag placeholders to temporary unique values; and
- maps old asset statuses to the new operational statuses.

The post-migration:

- converts technical placeholders to genuinely untagged assets;
- maps legacy condition selections to configurable condition records;
- fills legal owner and currency from the asset company where absent;
- preserves and classifies existing asset numbers;
- creates a default tag rule for each company lacking one; and
- records a migration event in immutable asset history.

No legacy business identifier is silently replaced.

## Configuration and permissions

No new environment variable or secret is introduced. Existing Microsoft Graph
and SharePoint credentials remain in the approved secret/configuration
boundaries.

Microsoft permissions are unchanged by this addon. Asset import uses the
existing SharePoint application/delegated permission set and the Operations
document library. Configure:

- an active Graph connection for each operating company;
- the `operations` SharePoint library mapping;
- the Asset and Asset Import storage policies;
- LHI asset state codes on Nigerian state records;
- category codes;
- one active default tag rule per company;
- approval matrices for `Asset Transfer` and `Asset Disposal`; and
- Asset Officer / Asset Manager / System Auditor group assignments.

## Verification performed

Executed in the development workspace:

- `python3 -m compileall -q custom-addons/lhi_asset_management`
- Python byte-code compilation of all Asset Register model and migration files
- standard-library XML parse of every Asset Register XML/template
- manifest parse and referenced-file existence check
- `git diff --check`

These static checks passed. A live Odoo registry, module upgrade, database
migration, QWeb/asset build, browser test, and transaction test were not
executed because the host Odoo runtime lacks required Python packages and the
Docker socket is not accessible. They remain release gates; this document does
not claim they passed.

Automated tests supplied cover:

- exact LHI-owned and project-owned tag formats;
- sequential tag allocation and unique sequence numbers;
- tag immutability;
- state transfer without tag mutation;
- approval-gated transfer completion;
- controlled re-tagging and segregation of duties;
- legacy tag preservation and classification;
- immutable lifecycle history; and
- denial for a minimal-access user.

## Deployment and rollback

Follow `docs/migration_and_rollback.md`. Production target remains
`https://work.lhinigeria.org` through Coolify. Back up and restore-test the
database before upgrade; deploy the exact Git commit; upgrade
`lhi_security,lhi_asset_management,lhi_programme_asset_bridge` on a database
copy first; then execute persona, report, import, SharePoint, browser-console,
and server-log checks.

Rollback is a database restore plus deployment of the prior image/commit.
Do not attempt to reverse the schema or delete migrated history manually.

## Remaining release risks and required approvals

- Database-copy migration and full Odoo tests are pending: owner, ERP technical
  lead; approval required before production.
- Concurrent tag allocation needs the supplied multi-worker test executed
  against PostgreSQL: owner, QA/ERP technical lead.
- SharePoint source/error upload and hash verification need tenant integration
  evidence: owner, Microsoft 365 integration administrator.
- QWeb PDF/barcode/QR rendering and dashboard asset-bundle/browser-console
  checks need a built Odoo container: owner, QA.
- Approval matrices are configuration, not demo data. Operations governance
  must approve the real transfer and disposal routes before go-live.
