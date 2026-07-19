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
model `lhi.award`. Media request, activity, success-story, and asset records use
that model for their grant/donor relationships. `lhi_funding_opportunity` is a
pre-award pipeline and is intentionally not used as the awarded-grant comodel.

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
