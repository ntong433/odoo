# Modification Sprint 3 delivery summary

## Outcome

Implemented `lhi_sharepoint_storage` as an independently installable,
policy-gated SharePoint storage foundation. Existing LHI RBAC remains
authoritative, technical attachments remain local, and business documents fail
closed with visible retry/reconciliation state.

## Changed files

New `lhi_sharepoint_storage` files:

- `README.md`, `delivery_summary.md`, `__init__.py`, `__manifest__.py`
- `controllers/__init__.py`, `controllers/document.py`
- `models/__init__.py`, `models/document_item.py`,
  `models/graph_connection.py`, `models/integration_job.py`,
  `models/ir_attachment.py`, `models/storage_policy.py`
- `security/ir.model.access.csv`,
  `security/lhi_sharepoint_storage_security.xml`
- `data/storage_policy_data.xml`, `data/ir_cron.xml`
- `views/document_item_views.xml`, `views/storage_policy_views.xml`,
  `views/lhi_sharepoint_storage_menus.xml`
- `static/src/js/sharepoint_many2many_binary.js`,
  `static/src/xml/sharepoint_many2many_binary.xml`,
  `static/tests/sharepoint_upload.test.js`
- `tests/__init__.py`, `tests/test_sharepoint_storage.py`
- `docs/administrator_guide.md`, `docs/deployment_and_rollback.md`,
  `docs/security_and_storage_architecture.md`

Existing-module integration changes:

- manifests and attachment views in `lhi_project_reporting`,
  `lhi_proposal_management`, `lhi_proposal_budget`, `lhi_grant_award`,
  `lhi_meal`, `lhi_purchase_request`, `lhi_project_compliance`,
  `lhi_vendor_management`, `lhi_project_issue`, and
  `lhi_project_amendment`;
- `lhi_signature_bridge/__manifest__.py`;
- `lhi_signature_bridge/models/lhi_opensign_request.py`;
- `lhi_signature_bridge/models/lhi_purchase_order_signature.py`;
- `lhi_signature_bridge/views/lhi_signature_bridge_views.xml`;
- `lhi_signature_bridge/report/lhi_purchase_order_report.xml`; and
- `lhi_signature_bridge/tests/test_signature.py`.

Odoo 19 compatibility corrections required to install and verify the changed
workflow chain:

- `lhi_base/views/menus.xml`;
- `lhi_donor_management/views/lhi_donor_views.xml`;
- `lhi_funding_opportunity/data/lhi_funding_cron.xml`,
  `models/lhi_donor_extension.py`, and its two primary view files;
- `lhi_grant_award/views/lhi_award_extension_views.xml`;
- `lhi_leave_bridge/data/ir_cron_data.xml`;
- `lhi_meal/data/ir_cron_data.xml`, `models/__init__.py`,
  `models/lhi_indicator.py`, `security/lhi_meal_security.xml`, and MEAL views;
- `lhi_procurement/views/lhi_procurement_views.xml`;
- `lhi_project_lifecycle/views/lhi_project_extension_views.xml`;
- `lhi_project_risk/views/lhi_project_risk_views.xml`;
- `lhi_project_workplan/data/ir_cron_data.xml`,
  `models/lhi_workplan.py`, and `views/lhi_workplan_views.xml`;
- `lhi_proposal_management/models/lhi_funding_opportunity_extension.py`,
  `models/lhi_proposal_section.py`, and `views/lhi_proposal_views.xml`;
- `lhi_proposal_budget/models/lhi_proposal_workspace_extension.py` and its
  budget/submission views;
- `lhi_purchase_request/models/lhi_purchase_request.py`;
- `lhi_reporting_hub/data/ir_cron_data.xml`; and
- `lhi_results_framework/models/lhi_indicator.py` and
  `views/lhi_indicator_views.xml`.

These corrections remove obsolete cron fields, convert legacy tree views to
Odoo 19 list views, repair missing dependencies/menu anchors, preserve
`mail.activity.mixin.activity_ids`, remove a Results Framework/MEAL circular
model reference, and reuse the existing results-element output model.

Deployment configuration:

- `.env.example`, `docker-compose.yml`, and `docker-compose.staging.yml`

## New models

### `lhi.document.item`

Stores document identity, file metadata, SHA-256/SHA-1/QuickXor hashes,
SharePoint site/drive/item/parent identifiers, URLs, ETags and versions,
business links, project/award/grant references, classification, workflow and
upload state, idempotency, reconciliation, requestor, temporary session state,
and restricted spool references.

### `lhi.document.storage.policy`

Stores model/field routing, backend, library role, folder strategy, size and
extension limits, metadata requirements, retention, confidentiality, conflict
behavior, direct-upload option, company, and sequence.

## Extended models and fields

- `ir.attachment`
  - `lhi_document_item_id`
  - `lhi_storage_state`
  - `lhi_remote_file_size`
- `lhi.integration.job`
  - `lhi_idempotency_key`
  - `lhi_operation_kind`
  - `company_id`
- `lhi.opensign.request`
  - SharePoint references for source, signed PDF, and certificate
  - storage status flags
  - source filename
- `lhi.workplan`
  - `workplan_activity_ids` replaces the conflicting business use of the
    chatter-reserved `activity_ids` name
- `lhi.indicator`
  - `workplan_activity_ids`
  - `meal_data_ids` is now supplied by `lhi_meal`, where its comodel exists
- `lhi.proposal.section`
  - `sequence`

## Implemented behavior

- small content uploads;
- resumable upload sessions with sequential 320 KiB-aligned chunks;
- persisted resume offsets and session expiry;
- delegated direct browser upload without Graph-token exposure;
- trusted post-upload streaming hash calculation;
- Odoo-generated document service;
- generated purchase-order PDF storage before OpenSign dispatch;
- signed PDF/certificate fail-closed callback quarantine;
- secure delegated download through the standard attachment route;
- application-context background reads;
- ETag-aware SharePoint recycle-bin deletion;
- explicit policy routing rather than global attachment replacement;
- protected temporary spool, post-commit removal, and orphan cleanup;
- exponential dead-letter retries and idempotent jobs;
- bounded reconciliation and session-expiry crons;
- structured redacted Graph and preauthenticated-content request logs;
- administrator and auditor diagnostics; and
- Python and Owl helper tests.

## New environment variable

- `LHI_SHAREPOINT_SPOOL_DIR`

No new secret is introduced.

## Required Entra permissions

No broader permission than the Sprint 2 design is required:

- application: Microsoft Graph `Sites.Selected`, assigned `write` only on the
  approved LHI ERP SharePoint site;
- delegated: `Sites.Selected` plus `openid`, `profile`, and `offline_access`,
  with explicit access to the approved site.

Do not grant tenant-wide `Files.ReadWrite.All` or `Sites.ReadWrite.All`.

## Required SharePoint configuration

- LHI ERP site and five validated libraries;
- explicit selected-permission assignment;
- Sprint 2 LHI metadata columns on every target library;
- versioning and recycle bin enabled;
- project folder template `01` through `09`;
- restricted Signed Documents permission boundary;
- approved retention category values; and
- sufficient service limits for selected file sizes and versioning.

## Database migration

Schema changes are handled by normal Odoo install/upgrade. No existing
attachment bytes are moved automatically. Existing-document migration remains
assigned to `lhi_document_migration`.

No custom SQL migration is required for the two business-field renames:

- `lhi.workplan.activity_ids` was a One2many alias over the existing
  `workplan_id` foreign key, so no relationship data is moved.
- `lhi.indicator.activity_ids` and `workplan_activity_ids` use the same
  implicit model-pair Many2many relation table, preserving existing links.

Historical OpenSign Binary attachments retain their existing Odoo field
semantics. New source, signed, and certificate bytes are temporary only and are
cleared after a SharePoint metadata record is created. Historical files are not
automatically migrated in this sprint.

## Automated test evidence

Executed on `lhi_erp_test`:

```text
python3 /opt/odoo/odoo/odoo-bin ... -u lhi_sharepoint_storage
  --test-enable --test-tags /lhi_sharepoint_storage

8 post-tests, 0 failed, 0 errors
```

Coverage includes:

- technical attachment exclusion;
- successful local-byte removal;
- failed upload spool and queue behavior;
- interrupted large-upload resume;
- storage-policy validation;
- metadata ACL denial for ordinary users;
- queue idempotency; and
- provisioned SharePoint column mapping.

Final Odoo log evidence:

```text
lhi_sharepoint_storage: 8 test methods, 0 failed, 0 errors
lhi_signature_bridge: 1 test method, 0 failed, 0 errors
```

The signature test covers generated purchase-order PDF storage, local-byte
clearing, signature locking, cancellation/unlocking, signed-PDF storage, and
fail-closed completion.

Additional executed checks:

- standalone module installation succeeded;
- module upgrade succeeded;
- a combined install/upgrade of all 12 changed business/storage modules
  succeeded across a 77-module dependency graph;
- Python bytecode compilation succeeded;
- all 176 LHI XML files parsed successfully in the Odoo container;
- JavaScript syntax checks succeeded with Node 20; and
- no embedded credentials or Graph tokens were found in changed integration
  source.

The Owl/HOOT helper test is present in `web.assets_unit_tests`. A browser-run
HOOT result is not claimed because the current Odoo container has no Chromium
binary.

## Manual test evidence

- Confirmed `lhi_sharepoint_storage` installed on the isolated test database.
- Confirmed all 12 targeted modules are installed.
- Confirmed the final 29 active policy records and three scheduled actions
  loaded.
- Confirmed new metadata tables and required/non-required columns were created.
- Live Microsoft tenant upload, download, Office preview/edit, deletion, and
  OpenSign callback tests were not executed because no tenant credentials or
  production data were used in the workspace.
- Browser Hoot execution was not performed because the current container does
  not include Chromium.

## Deployment and rollback

See `docs/deployment_and_rollback.md`.

## Remaining risks

- Live SharePoint throttling, tenant retention, and browser upload CORS behavior
  require staging evidence.
- Browser-only large uploads require the user to retain the source file to
  restart an expired session.
- Existing business bytes remain local until the later controlled migration.
- Historical OpenSign attachments require inventory and controlled migration
  before local storage can be retired.
- Full Hoot browser execution is pending a test image with Chromium.
- The isolated test database logs a pre-existing missing filestore object while
  rendering reports. It did not fail the executed tests, but staging filestore
  integrity should be checked before deployment.
- SharePoint upload is an external side effect; database rollback after remote
  completion can create an orphan DriveItem. Audit correlation IDs and the
  later migration/reconciliation tooling must quarantine such items.
