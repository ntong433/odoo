# LHI Media & Communications

This module provides the Media and Communications workflows for LHI, integrating with the core `lhi.project` system and managing SharePoint document sync for media assets and consent forms.

## Features

- Media Requests
- Content Calendar & Activities
- Success Stories
- Photography, Video, Audio Production
- Approvals & Consent Controls
- Project & Programme Integration

## Dependencies and grant relationship

The module depends on `lhi_base`, which defines the canonical awarded-grant
model `lhi.award`, and on `lhi_project_workplan`, which defines
`lhi.workplan.activity`. Media request, activity, success-story, and asset
records use those models for their grant/donor and workplan relationships.
`lhi_funding_opportunity` is a pre-award pipeline and is intentionally not used
as the awarded-grant comodel.

## Access roles

The module provides dedicated Media Viewer, Requester, Officer, Reviewer, and
Manager roles. These roles imply ordinary internal-user access only; they do not
grant Access Rights or module-administration privileges.

## Installation and verification

Install `lhi_base` before this module (the manifest enforces this automatically),
then install or update `lhi_media_communications`. Run the focused registry test
on a disposable database with:

```bash
python3 odoo/odoo-bin --addons-path=odoo/addons,custom-addons \
  -d <test_database> -i lhi_media_communications --test-enable \
  --test-tags /lhi_media_communications --stop-after-init --no-http
```

No new environment variables, secret-store entries, Microsoft Graph permissions,
SharePoint configuration, database migration scripts, or production data are
introduced by this registry correction. The ORM creates no new columns; existing
Media grant/donor columns retain their integer foreign-key storage and now resolve
to the registered `lhi.award` model.

Rollback by restoring the preceding application commit and updating this module
on a backed-up database. Do not roll back after Media records have been linked to
awards without first checking those references. Production deployment remains a
separate, approved Coolify maintenance operation for
`https://work.lhinigeria.org` after disposable-database verification.

## Project-view activation correction

The Media integration inherits `lhi_base.view_lhi_project_form` on the canonical
`lhi.project` model. That parent form contains a `sheet` but no `button_box`, so
the Media view inserts its supported smart-button box through `//sheet`. All four
buttons retain their existing computed count fields and server action methods.
This correction adds no schema, migration, environment, secret-store, Microsoft,
or SharePoint configuration changes. Python compilation and XML well-formedness
checks passed; disposable database installation and production browser evidence
must be collected in the Coolify runtime before production sign-off.

## User access-rights compatibility

The stable Media module-category and `res.groups.privilege` records use the
backend label `Media and Communications`. This avoids unsafe special characters
in Odoo 19's generated user access-rights view while preserving the friendly
`Media & Communications` application and menu labels. Existing XML IDs, group
relationships, ACLs, and user assignments are unchanged.
