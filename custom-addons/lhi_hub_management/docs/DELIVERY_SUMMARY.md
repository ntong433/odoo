# HUB delivery summary

## Changed architecture

The new `lhi_hub_management` addon combines the recommended HUB, approval,
external-transaction, lease, dashboard, and operational-structure boundaries
around the existing Odoo `stock.*` models. It reuses `lhi_asset_management`,
`lhi_approval_matrix`, `lhi_signature_bridge`, `lhi_sharepoint_storage`,
`lhi_inventory`, `lhi_audit`, `lhi_security`, and `lhi_web_shell`. No core file
was modified.

`lhi_approval_matrix/models/lhi_approval_request.py` was also hardened so
submitted approvals authorize only the frozen request-line approver snapshot,
not later matrix configuration.

## New models

- `lhi.hub.consignment` and line
- `lhi.hub.stock.request`, line, immutable document version, and artifact
- `lhi.hub.external.issue` and line
- `lhi.hub.equipment.lease`, line, and lease payment
- `lhi.hub.stock.adjustment` and line
- `lhi.hub.payment.method`
- immutable `lhi.hub.operational.revenue`
- `lhi.hub.notification`

## Extended models and fields

- `res.users`: authorized HUBs
- `res.partner`: external-recipient classification and minimized context
- `stock.warehouse`: state, office, team, authorization, controlled locations
- `product.category`: protected HUB category code
- `product.template`: tracking policy, operational value, control/lease/asset
  configuration
- `stock.lot`: expiry, quarantine, donor/project/consignment, controlling HUB,
  Asset Register link
- `stock.quant`: operational stock value
- `stock.picking` / `stock.move`: immutable source provenance
- `stock.move`: controlled-adjustment provenance
- `lhi.asset`: stock lot/serial link
- approval matrix/request/line/history: HUB criteria, roles, signer snapshot,
  provider-confirmed decisions
- `lhi.audit.log`: HUB operational event type

Database schema additions are created by the standard Odoo ORM upgrade. The
post-migration script classifies existing category descendants and backfills
controlling HUBs for resolvable lots. No pre-migration SQL and no accounting
schema change is introduced.

## Changed files

- addon/package: `__init__.py`, `__manifest__.py`, `models/__init__.py`;
- models: `hub_structure.py`, `hub_product.py`, `hub_consignment.py`,
  `hub_request.py`, `hub_external_issue.py`, `hub_lease.py`,
  `hub_adjustment.py`, `hub_notification.py`, `hub_asset_notification.py`, and
  `hub_dashboard.py`;
- security/data: `security/lhi_hub_security.xml`,
  `security/ir.model.access.csv`, all four `data/lhi_hub_*_data.xml` files,
  and `migrations/19.0.1.0.0/post-migrate.py`;
- UI/assets: all eight workflow/configuration/menu view XML files plus
  `views/lhi_hub_adjustment_views.xml`, the dashboard JS/XML/SCSS files, and
  `static/tests/hub_dashboard.test.js`;
- reports: `report/lhi_hub_reports.xml` and
  `report/lhi_hub_report_templates.xml`;
- tests: `tests/common.py`, `tests/test_hub_operations.py`,
  `tests/test_hub_security.py`, and `tests/test_hub_workflows.py`;
- documentation: `README.md` and every file under `docs/`; and
- reused engine hardening:
  `lhi_approval_matrix/models/lhi_approval_request.py`; and
- stable Programmatic Operations naming:
  `lhi_base/views/menus.xml` and
  `lhi_programme_management/views/programme_menus.xml`.

The prerequisite operational role definitions are in
`lhi_security/security/security_groups.xml` and were delivered in the earlier
platform-decoupling phase.

## Security

The addon configures HUB Viewer, Warehouse Officer, Operations Officer,
Operations Manager, Director of Operations, NED, Programme User/Approver,
Asset roles, System Auditor, Integration Service, and ERP Administrator
access. ACLs and record rules cover company, assigned HUB, creator, current
approver, organization-wide Director scope, and read-only audit scope.
Stock adjustment validation is restricted to Operations Management. A
process-local workflow sentinel prevents RPC callers from forging internal
context flags.

## Configuration and secrets

No new environment variable or secret-store key is required. The optional,
non-secret Odoo system parameter `lhi_hub.expiry_alert_days` defaults to 90 and
is bounded to 1–365. Existing LHI Sign, SharePoint/Graph, webhook, Entra, and
outbound-mail secrets remain unchanged. No new Graph permission is requested.
SharePoint requires the existing least-privilege application to reach the
configured Operations, Controlled Documents, and Signed Documents libraries.

## Verification performed in this workspace

Executed successfully:

- `python3 -m compileall -q custom-addons/lhi_hub_management custom-addons/lhi_approval_matrix`
- Odoo 19 virtual-environment import of `lhi_hub_management`
- Odoo 19 virtual-environment import of all HUB test modules
- XML well-formedness checks for all addon XML files
- manifest data-file existence check
- duplicate XML-ID and ACL-ID checks
- Ruff undefined-name/static Python checks
- Ruff formatting check
- `git diff --check`

Automated tests added cover assigned-HUB isolation, auditor workflow denial,
immutable approval snapshots, negative-stock blocking, validated issue
movements, operational revenue, notification deduplication, pharmaceutical
tracking, active-serial lease conflicts, immutable payments, and reversing
revenue. They also cover forged workflow-context denial and a reason-controlled
stock adjustment/reversal with before/after quantities and an inventory move,
low-stock alert recipient queuing, and frontend dashboard normalization,
formatting, warning isolation, and drill-down validation.

Not executed here:

- registry creation, module installation/upgrade, migrations, or Odoo test tags;
- PostgreSQL transaction/concurrency tests;
- Owl asset build and browser persona/console tests;
- LHI Sign API/webhook/reconciliation contract tests against a provider;
- SharePoint upload/download/hash verification;
- clean-container/Coolify rebuild.

Reason: no PostgreSQL listener is available and the Docker socket is
permission-denied in this workspace. These are release gates, not reported as
passing.

## Manual staging scenarios

Run the 14 personas from the project requirements, including a newly
synchronized Entra user without an employee record. Capture redacted evidence
for dashboard/sidebar, HR absence, Fleet/Procurement visibility, assigned-HUB
isolation, all stock workflows, three-step LHI Sign route, document hashes,
negative/concurrent stock protection, notification degradation, and absence of
accounting records.

## Remaining risks and approvals

- Staging registry/test/provider validation remains mandatory. Owner:
  deployment engineer; approval: Operations, Security, and ERP product owner.
- Legacy lots whose current location does not resolve to a HUB require an
  approved mapping before officer access. Owner: Warehouse Operations.
- Matrix thresholds, delegates, signer identities, and signature coordinates
  require business approval. Owner: Director of Operations/NED.
- SharePoint library, retention, content type, webhook, and least-privilege
  connection configuration require Microsoft 365 approval. Owner: M365
  administrator.
- Production activation requires backup/restore evidence, staging results,
  rollback rehearsal, and Coolify cutover approval.
