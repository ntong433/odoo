# Coolify deployment and rollback

## Environment variables

Configure these in Coolify, not in source control:

- `LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS`: comma-separated approved VPN,
  Cloudflare Access egress, or administrator source CIDRs.
- `LHI_ENTRA_TRUST_PROXY_HEADERS`: `true` only when the trusted Coolify proxy
  overwrites and sanitizes `X-Forwarded-For`.

The module reuses the Graph core environment-only client-secret token service.
The secret is configured in protected Coolify settings and is never stored in
Odoo or source control.

## Entra application configuration

- Redirect URI: `https://work.lhinigeria.org/auth_oauth/signin`
- Delegated sign-in scopes: `openid`, `profile`, `email`, `User.Read`
- Application permissions: `User.Read.All`, `GroupMember.Read.All`
- Existing SharePoint permission: `Sites.Selected`, assigned only to the approved
  LHI ERP SharePoint site.

Odoo 19 `auth_oauth` currently uses an access-token response from the authorization
endpoint. Enable the web application's access-token implicit grant for this
provider. Microsoft recommends authorization-code flow for new applications; this
is a documented compatibility risk pending a future Odoo authentication adapter.

## Deployment

1. Back up PostgreSQL and the Odoo data volume.
2. Deploy the changed custom addons and environment variables.
3. Upgrade `lhi_integration`, `lhi_approval_matrix`, then install or upgrade
   `lhi_entra_identity_sync`.
4. Keep scheduled actions disabled.
5. Configure mappings and complete staging dry-run/write evidence.
6. Validate both maintenance accounts through the protected route.
7. Enable primary SSO and scheduled reconciliation during the approved window.
8. Verify `/web/health`, OAuth redirect, Graph diagnostics, cron execution, and
   worker logs in Coolify.

Production must keep `web.base.url` frozen at `https://work.lhinigeria.org`.
Protect `/lhi/maintenance/login` with Cloudflare Access, VPN, or equivalent proxy
policy in addition to the module's CIDR check.

## Rollback

For an individual synchronization run, use **Rollback**. Rollback proceeds only
when the current user state still matches the recorded post-sync hash; it refuses
to overwrite newer local changes.

For deployment rollback:

1. Disable primary SSO and both Entra scheduled actions.
2. Roll back applied synchronization runs where required.
3. Use a protected maintenance administrator to verify local access.
4. Restore the previous image/custom-addons revision.
5. Upgrade the affected modules only if the rollback revision requires it.
6. Restore PostgreSQL from the pre-deployment backup only when schema rollback is
   required and approved.

Do not uninstall the module as a routine rollback: uninstalling would remove sync
diagnostics and snapshots needed for audit.
