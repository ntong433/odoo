# LHI Programs and Grants

This addon coordinates donor-funded project execution around the canonical
`lhi.project` model. It adds project budgets, activity allocations, approval-
gated memos, execution requests, retirements, and contextual links to existing
departmental modules. It does not create journal entries or replace LHI's Odoo
Enterprise accounting system.

Department addons do not depend on this hub. They remain directly accessible
and keep standalone workflows. Installing this hub adds optional project/grant/
activity/memo/budget context to their existing records.

Persistent business-document bytes remain in SharePoint through
`lhi.document.item`; the lifecycle models store metadata relationships only.

## Deployment

Install or update only the affected modules on a disposable database first.
No environment variables, secrets, Microsoft Graph permissions, SharePoint
tenant configuration, or accounting migration is introduced. The new tables
are created by the ORM. Deploy through Coolify for
`https://work.lhinigeria.org` after backup and test evidence.

Rollback by restoring the preceding code commit and database backup. If records
have been created in these new lifecycle tables, export and reconcile them
before uninstalling or reverting the module.
