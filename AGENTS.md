# LHI Nigeria ERP — Project Engineering Instructions

These instructions apply to all work in this workspace. They are mandatory for developers and coding agents unless an approved, documented exception says otherwise.

## Project baseline

- Target Odoo 19 Community on the `19.0` branch of `https://github.com/ntong433/odoo.git`.
- Use two-week delivery sprints.
- Deploy production through Coolify with `https://work.lhinigeria.org` as the canonical public production URL.
- Keep Odoo Enterprise as LHI's official accounting system until the approved accounting migration cutover.
- Deliver operational modules before the Accounting migration.
- Integrate the existing Leave Management capability; do not rebuild it.
- Use LHI OpenSign for configured final signatures, Microsoft Entra ID for organizational identity, and Power BI for portfolio and executive analytics.
- Use Microsoft Entra ID as the primary authentication provider. Retain protected local Odoo administrator accounts for maintenance and recovery access.
- Use SharePoint Online as the system of record for all LHI business-document bytes. Provide document preview and management in Odoo and open Word, Excel, and PowerPoint for the web in a new browser tab for editing.

## Repository and extension policy

- Inspect the repository, installed addons, custom modules, and applicable instructions before making changes. Reuse existing models and components and avoid duplicate functionality.
- Put all LHI modules in the workspace-level `custom-addons/` directory, outside `odoo/` and its core addon paths.
- Do not modify Odoo core. Use inheritance, extension hooks, services, registries, controllers, and supported asset bundles. A core change is permitted only when no extension mechanism exists; document the reason, alternatives considered, affected core files, upgrade risk, and approval.
- Prefix custom modules with `lhi_`. Apply the `lhi_` namespace to new models where appropriate and to XML IDs, security groups, JavaScript registries, scheduled actions, and configuration keys.
- Use Odoo ORM APIs and Odoo 19 conventions. Avoid direct SQL unless it is necessary, safe, parameterized, and documented.
- Never commit secrets, passwords, API keys, tenant secrets, certificates, Graph tokens, SharePoint resource identifiers, production database credentials, webhook secrets, or private integration endpoints. The canonical public URL `https://work.lhinigeria.org` may be documented where required. Store sensitive configuration in access-restricted Odoo settings/system parameters, environment variables, or an approved secret store, and mask secrets in logs and error messages.

## Authoritative identity, authorization, and document boundaries

- Microsoft Entra ID supplies authentication and synchronized organizational identity attributes, including manager relationships, departments, offices, and explicitly configured functional-group memberships.
- Entra ID is not a second authorization engine. Existing Odoo RBAC remains authoritative for authorization, including `lhi_security`, approval matrices, record rules, project assignments, segregation-of-duties controls, and protected administrator roles.
- Inspect all existing `lhi_` modules before implementation. Reuse and extend existing modules, groups, roles, models, workflows, integrations, and security controls rather than recreating them.
- SharePoint Online stores all persistent LHI business-document bytes. Odoo stores only business relationships, document metadata, workflow state, permission mappings, audit references, immutable SharePoint item identifiers, and strictly bounded temporary processing data.
- Business-document uploads must fail closed. An Odoo record must not claim that a document is safely stored until SharePoint confirms the upload and Odoo durably records the returned immutable item identifier.
- Existing LHI OpenSign remains the signature platform. Integrate document workflows with it rather than introducing a parallel signature mechanism.

## Required module contents

Every LHI module must include, as applicable:

- a valid Odoo 19 `__manifest__.py` with explicit dependencies, ordered data files, standard asset bundles, a license, and an Odoo 19 version;
- initialized Python packages, models, business constraints, and database constraints where appropriate;
- dedicated groups, least-privilege access-control entries, and record rules, including multi-company isolation where relevant;
- actions, menus, and Odoo 19 views for supported workflows;
- chatter tracking and activities for auditable business events where relevant;
- scheduled actions with namespaced XML IDs, bounded batches, safe retries, and idempotent processing where relevant;
- Python tests and frontend tests whenever Owl components or other JavaScript behavior are introduced;
- installation and upgrade verification;
- administrator configuration documentation and user-facing workflow documentation; and
- a delivery summary listing changed files, migrations, configuration, and test results.

If an item does not apply, state why in the module documentation or delivery summary rather than silently omitting it.

## Security requirements

- Enforce authorization on the server. Hidden menus, views, fields, or buttons are usability controls, not security controls.
- Apply least privilege at both model and record level. Do not create ungrouped ACLs or global record rules unless intentionally required and security-reviewed.
- Use dedicated LHI business groups rather than granting technical administration privileges.
- Treat controller routes, RPC methods, webhooks, scheduled jobs, imports, exports, reports, and integration callbacks as security boundaries. Validate identity, authorization, ownership, company scope, input, and state transitions server-side.
- Minimize `sudo()` use. Narrow its scope, justify it in code, and never use it to bypass business authorization accidentally.
- Protect integration endpoints against replay, forgery, duplicate delivery, data leakage, and unsafe retries. Log auditable outcomes without logging credentials or sensitive payloads.
- Preserve immutable or traceable audit history for approvals, signatures, sensitive configuration changes, and important workflow transitions.

## Data policy

- Never load production dummy, sample, or placeholder business records.
- Put demonstration records only in manifest `demo` files so they load solely when demo data is enabled.
- Create test records only inside automated test setup/fixtures and ensure they cannot be loaded by normal production installation or upgrade.
- Keep reference/configuration data in normal data files only when it is required for real operation, deterministic, documented, and safe for production.
- Do not use production personal or confidential data in demos, fixtures, screenshots, or tests.

## Accounting feature gate and cutover

- Develop the new LHI Accounting capability behind a formal `lhi_`-namespaced feature flag that defaults to disabled and fails closed.
- The production flag must not be activated by module installation, upgrade scripts, demo data, scheduled actions, or ordinary users.
- While disabled, block Accounting menus, client actions, server operations, scheduled jobs, integrations, and mutation endpoints. Server-side checks remain mandatory even when UI elements are hidden.
- Keep the capability disabled in production until authorized stakeholders approve the migration, reconciliation, security review, test evidence, rollback plan, and cutover.
- Record activation and deactivation in the audit trail. Document the authorized activation procedure, prerequisites, verification checks, and rollback procedure.

## Engineering and UI standards

- Use constraints for invariants and explicit transition methods for workflows. Validate allowed source and destination states on the server.
- Use chatter, activities, scheduled actions, and standard Odoo services instead of parallel custom frameworks where they meet the need.
- Build frontend behavior with Odoo 19 Owl patterns, services, registries, templates, and standard asset bundles. Namespace registry keys and avoid patching global behavior unless justified and tested.
- Make integrations configurable, timeout-bound, observable, retry-safe, and tolerant of partial failure. Prevent duplicate remote and local records with stable idempotency keys or unique constraints.
- Follow accessible, translatable, multi-company-aware, and timezone-safe implementation patterns.

## Integration reliability and operations

Every Entra ID, Microsoft Graph, SharePoint, OpenSign, Power BI, webhook, and other external integration must include, where applicable:

- stable idempotency keys and duplicate-delivery prevention;
- complete pagination with bounded page and record processing;
- timeout-bound retries with exponential backoff and jitter;
- explicit rate-limit detection and `Retry-After` handling;
- durable failure queues with bounded, safe, administrator-controlled replay;
- scheduled and on-demand reconciliation that detects and reports drift;
- structured, correlation-friendly logs that exclude credentials, tokens, document bytes, and sensitive payloads;
- administrator diagnostics that expose health, backlog, last success, safe error details, and reconciliation status;
- least-privilege application and delegated permissions, documented with justification;
- authentication, authorization, ownership, company-scope, replay, forgery, and state-transition validation at every integration boundary;
- automated tests for success, pagination, retry, throttling, timeouts, malformed responses, duplicates, replay, partial failure, queue handling, and reconciliation; and
- installation and upgrade tests plus administrator, operational, deployment, and recovery documentation.

## Required automated verification

Tests must cover the behavior affected by each change, including:

- installation and upgrade of every changed module;
- ACL permissions for ordinary users, managers, administrators, portal/public users where applicable, and unauthorized users;
- record isolation by owner, team, company, and other applicable business boundaries;
- permitted and forbidden workflow transitions, including attempts through RPC or direct ORM calls;
- Python and database constraints, concurrency-sensitive uniqueness, and duplicate prevention;
- feature-flag behavior, especially server-side denial while Accounting is disabled;
- integration success, authentication failure, timeout, malformed response, retry, duplicate callback, replay, and partial failure;
- scheduled-action idempotency and failure isolation; and
- Owl components and frontend behavior with the appropriate Odoo JavaScript test framework.

Run tests with non-superuser identities where authorization is under test; `sudo()` invalidates record-rule coverage. Do not report a test as passed unless it was executed. Record commands, outcomes, and any untested areas in the delivery summary.

## Definition of done

A change is complete only when its code, security controls, tests, installation/upgrade checks, configuration guidance, user workflow guidance, and changed-file/test summary are present and consistent. Any exception or deferred verification must be explicit, risk-assessed, assigned, and approved.

Each sprint delivery summary must explicitly include:

- changed files;
- new and changed models and fields;
- new or changed environment variables and secret-store entries, without secret values;
- required Microsoft Entra and Graph permissions, with least-privilege justification;
- required SharePoint tenant, site, library, content-type, permission, webhook, and retention configuration;
- database schema changes, migration scripts, pre-migration checks, and post-migration verification;
- automated test commands and actual results;
- manual test scenarios and evidence, with sensitive data redacted;
- Coolify deployment and configuration instructions using `https://work.lhinigeria.org`;
- rollback procedure for code, configuration, database, queues, webhooks, and integration state; and
- remaining risks, deferred verification, owners, mitigations, and required approvals.
