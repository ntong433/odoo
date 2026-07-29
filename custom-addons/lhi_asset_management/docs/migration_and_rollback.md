# Asset Register Migration, Deployment, and Rollback

## Mandatory pre-migration gate

1. Freeze Asset Register writes for the maintenance window.
2. Record the current Git commit and container image digest.
3. Create a PostgreSQL database backup and verify it can be restored to an
   isolated database.
4. Back up the Odoo filestore and the SharePoint/Graph configuration metadata
   without exporting secret values into Git or logs.
5. Run the upgrade first against a production database copy.
6. Resolve every duplicate tag, duplicate same-company serial number, or unsafe
   category code as a governed data-quality decision. The migration intentionally
   stops instead of silently changing identifiers.

## Database-copy upgrade

Deploy the candidate image built from the reviewed commit, then upgrade in this
order:

```text
lhi_security
lhi_asset_management
lhi_programme_asset_bridge
```

Use the deployment's normal Odoo module-upgrade command with the production
addons path and database-copy credentials. Do not put credentials in shell
history, documentation, or Git.

Verify:

- old asset counts and total operational values reconcile;
- every legacy Asset Number is unchanged;
- technical `New`/`/` placeholders became untagged, not invented tags;
- legacy status and condition mappings are correct;
- the migration-history event exists;
- all company tag rules exist;
- no duplicate tag/serial constraint failure remains;
- approval, dashboard, QWeb, SharePoint, and persona tests pass; and
- server and browser logs contain no registry, RPC, Owl, action, or access error.

## Coolify deployment

Build and deploy the exact reviewed commit to the existing Coolify service for
`https://work.lhinigeria.org`. Preserve the existing PostgreSQL volume,
SharePoint spool volume, environment configuration, and protected secrets.
Upgrade modules as a controlled release step. Restart and repeat smoke tests
after container recreation.

## Rollback

If a release gate fails:

1. stop application writes;
2. retain failed migration/server logs with secrets redacted;
3. deploy the previous image/commit;
4. restore the pre-upgrade database backup;
5. restore the matching filestore if it changed;
6. do not delete SharePoint files created during testing—reconcile and archive
   them using their immutable item IDs;
7. reconcile any provider/notification queues before reopening access; and
8. verify login, dashboard, sidebar, Asset Register, procurement, fleet,
   Entra ID, memo, SharePoint, and signature workflows.

Schema downgrade or manual history deletion is not an approved rollback.
