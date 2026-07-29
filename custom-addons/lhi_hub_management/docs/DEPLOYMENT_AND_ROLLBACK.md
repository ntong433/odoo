# Deployment, migration, and rollback

Canonical production URL: `https://work.lhinigeria.org`.

## Mandatory pre-deployment backup

Before installing/upgrading on any non-disposable database:

1. create and verify a PostgreSQL database backup;
2. back up the Odoo filestore even though HUB business documents use
   SharePoint;
3. export current installed-module/version state;
4. record current SharePoint/LHI Sign connection and webhook configuration
   without exporting secret values;
5. snapshot Coolify service configuration and image tag; and
6. test database and filestore restoration on an isolated copy.

Do not uninstall HR or any module as part of this deployment.

## Pre-migration checks

- identify protected-category name/code conflicts;
- verify warehouse codes are unique;
- verify each operational user has the correct LHI role and assigned HUB;
- verify existing lots resolve to at most one current internal HUB;
- review unassigned/negative quants and duplicate serials;
- verify existing HUB matrices have deterministic stages and eligible active
  users;
- verify all signature users have email and Entra object ID; and
- verify SharePoint policies resolve and perform a non-production upload/hash
  round trip.

Stop on unsafe conflicts. Do not overwrite legacy identifiers.

## Coolify deployment

1. Build the repository commit containing `custom-addons/lhi_hub_management`.
2. Mount the workspace `custom-addons` path in Odoo's addon path.
3. Keep database, Graph, SharePoint, OpenSign, webhook, and SMTP secrets in
   Coolify/approved secret storage. This addon adds no environment variable.
4. Deploy a saved image/version to staging.
5. Run:

   ```bash
   odoo-bin -d <staging_db> -u lhi_security,lhi_approval_matrix,lhi_asset_management,lhi_hub_management --stop-after-init
   ```

6. Run the tagged Python tests and browser persona checklist on staging.
7. Validate SharePoint source/signed/certificate uploads and one LHI Sign
   sandbox route.
8. Rebuild/restart the staging service and repeat smoke checks.
9. Obtain change, security, migration, and cutover approval before production.
10. Deploy the same immutable image to `https://work.lhinigeria.org`, upgrade
    modules, and retain logs/evidence.

## Post-deployment validation

- module installation/upgrade has no registry warnings;
- Operations/HUB and Asset dashboards load for every persona;
- no HR menu is visible and Fleet/Procurement remain under Operations;
- unauthorized HUBs/lots/pickings are absent;
- standard locations, protected categories, FEFO, sequences, and crons exist;
- one consignment receipt changes stock only after picking validation;
- one external issue and reversal reconcile stock and operational revenue;
- one positive and negative stock adjustment records reason, before/after
  quantities, inventory move, and auditable reversal without negative stock;
- one serial lease/release/return prevents double allocation;
- one full LHI Sign route advances only by provider confirmation;
- final PDF, certificate, dispatch note, and receipt confirmation have verified
  SharePoint item IDs/hashes;
- missing SMTP produces a retained queue state, not a rollback;
- no `account.move`, invoice, journal, or accounting payment is created; and
- server, browser console, workers, crons, queues, and webhook logs are clean.

## Rollback

If code fails before production transactions, restore the prior image and
database/filestore backup. If transactions exist, do not simply uninstall the
module:

1. stop intake and scheduled HUB jobs;
2. disable provider/webhook delivery at the connection boundary;
3. export notification backlog, LHI Sign request IDs, SharePoint item IDs,
   open reservations/pickings, and operational document states;
4. reverse completed stock movements through controlled returns—not SQL;
5. reconcile remote LHI Sign and SharePoint artifacts by immutable ID;
6. restore the database and filestore backup when approved;
7. deploy the prior immutable image;
8. restore webhook/queue configuration only after reconciliation; and
9. document remote artifacts created after the backup and retain them under
   the approved retention policy.

The migration only classifies blank HUB item types under protected category
trees and assigns blank controlling-HUB values from current internal lot
locations. It does not modify quantities, asset tags, approval history,
signature state, document bytes, or accounting data. Reverting those
classifications requires an approved mapping captured before upgrade.
