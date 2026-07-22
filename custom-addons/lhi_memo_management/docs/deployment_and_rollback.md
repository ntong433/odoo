# Deployment, verification, and rollback

## Pre-deployment

1. Back up the production database and verify the SharePoint/provider
   configuration without printing secrets.
2. Deploy the pushed Git commit through Coolify and verify the active container
   contains `custom-addons/lhi_memo_management`.
3. Set `LHI_OPENSIGN_API_TOKEN` and `LHI_OPENSIGN_WEBHOOK_SECRET` in the
   protected Coolify secret store, or configure protected system parameters.
4. Test on a disposable production-like database first.

Example targeted disposable command inside the Odoo container:

```bash
python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf \
  -d lhi_memo_test \
  -u lhi_approval_matrix,lhi_signature_bridge,lhi_dashboard,lhi_web_shell \
  -i lhi_memo_management \
  --test-enable \
  --test-tags /lhi_memo_management,/lhi_signature_bridge,/lhi_approval_matrix,/lhi_dashboard,/lhi_web_shell \
  --stop-after-init \
  --http-port=18069 \
  --gevent-port=18072 \
  --max-cron-threads=0 \
  --logfile=/tmp/lhi-memo-test.log
```

The process must exit `0`. Never use `-u all`.

## Targeted production install/update

After disposable success and a fresh backup, resolve the protected production
database name into `LHI_PRODUCTION_DB`, then run:

```bash
test -n "$LHI_PRODUCTION_DB" && \
python3 /opt/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf \
  -d "$LHI_PRODUCTION_DB" \
  -u lhi_approval_matrix,lhi_signature_bridge,lhi_dashboard,lhi_web_shell \
  -i lhi_memo_management \
  --stop-after-init \
  --http-port=18069 \
  --gevent-port=18072 \
  --max-cron-threads=0 \
  --logfile=/tmp/lhi-memo-production.log
```

Restart the normal Odoo container. Do not repeatedly activate modules through
the production UI.

## Post-deployment checks

- Employee sees Memos and not Signature Administration.
- Signature Administrator sees Signature Administration.
- Create a non-confidential test memo using approved test identities.
- Word opens on the existing ERP SharePoint site.
- PDF capture stores a stable DriveItem ID and SHA-256 hash.
- Preparation opens in a new tab and same-tenant Entra sign-in is enforced by
  OpenSign.
- Required requester/final fields are validated.
- Requester signs first; approvers act strictly in order; final authority signs
  last.
- Return/resubmit creates a new hash and provider request while preserving the
  old one.
- Completed PDF and certificate both exist in SharePoint before Completed.
- Invalid webhook signatures return HTTP 401 and duplicate events do not repeat
  business actions.
- Browser console and Odoo logs have no Owl, access, registry, or traceback
  errors.

## Rollback

1. Stop normal Odoo traffic and jobs.
2. Revoke/disable the new webhook at OpenSign if callback behavior must stop.
3. Roll back the Coolify deployment to the prior image/commit.
4. Restore the pre-deployment database backup if the new module was installed
   or its schema/data loaded; code rollback alone is not a schema rollback.
5. Restore prior provider/system-parameter configuration without exposing
   secret values.
6. Reconcile active provider requests and SharePoint integration jobs before
   reopening traffic. Do not delete provider envelopes, signed documents,
   certificates, webhook history, or SharePoint DriveItems.
