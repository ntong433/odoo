# Microsoft Login and Entra Synchronization Completion Report

## Scope and root-cause audit

The repository contained no custom route replacing `/auth_oauth/signin` and no
hardcoded `oauth_provider_id=4`. The prior production HTTP 500 cannot be
attributed conclusively without the corresponding secret-redacted Odoo traceback
and reverse-proxy request ID. The audited implementation did contain two material
design defects capable of breaking first login: it treated the native validation
`user_id` as the immutable Graph object ID without a delegated `/me` lookup,
and the synchronization engine blocked every directory identity that did not
already have an Odoo user. Both defects are corrected.

The existing uncommitted controller remediation was preserved. It removes the
automatic redirect loop from `/web/login`, keeps Odoo's native provider listing
and login handling, and records protected maintenance login only after a valid
local session exists.

## Implemented behavior

- Stable provider XML ID:
  `lhi_entra_identity_sync.oauth_provider_microsoft_entra`. The post-install
  hook aliases the established provider record instead of creating a duplicate.
- Provider configuration is tenant-scoped, uses `openid profile email`,
  `https://graph.microsoft.com/oidc/userinfo`, the Windows icon class, Odoo's
  native callback, and the generated provider `auth_link`.
- `auth_oauth.authorization_header=1`, frozen
  `https://work.lhinigeria.org`, and the callback URL are configured by the
  guarded administrator action.
- Native OAuth validation runs first. A bounded server-side Graph `/me` request
  then supplies the immutable object ID and account status. First-login linking
  calls the native signin hook first with user creation disabled, then links only
  one active, synchronized, approved, tenant-consistent, non-protected user.
- The branded login page selects the Microsoft provider by stable XML ID and uses
  only `provider.get('auth_link')`. It contains no hand-built authorization or
  callback URL and no browser-side token logic.
- Full or scoped synchronization can plan and create actual internal
  `res.users` records. Creation is dry-run visible, idempotent by immutable
  object ID, normalized by UPN, company-scoped, and starts with the approved
  `lhi_security.group_lhi_employee` baseline.
- User creation uses `no_reset_password`, `mail_create_nosubscribe`,
  `tracking_disable`, and `mail_notrack`. Scheduled sync forces those contexts.
  The invitation setting defaults to false and cannot be enabled until a separate
  approved manual workflow exists.
- Graph user selection includes all requested identity properties. Existing Graph
  core pagination, bounded retries, `Retry-After` support, manager retrieval,
  mapped-group batching, protected-group handling, dry-run planning, idempotency
  keys, failure queue, and rollback snapshots remain in use.
- The dashboard has one component registration:
  `lhi_dashboard.dashboard_action`. Its first root menu provides the normal Odoo home action;
  explicit deep links remain under the standard Odoo router.

## Changed modules and schema

- `lhi_entra_identity_sync`
  - new configuration fields: `create_missing_users` and
    `send_invitation_emails_after_sync`;
  - `lhi.entra.sync.plan.user_id` is nullable during a creation dry run;
  - new plan match value `create`;
  - new audit event value `identity_link`.
- `lhi_web_shell`: stable-provider native login link.
- `lhi_dashboard`: canonical client-action key and removal of the unused home
  router from the asset bundle.

No Odoo core file is modified. No migration script is required; Odoo's module
upgrade creates the additive columns and selection metadata. Pre-upgrade, verify
that the established provider XML ID exists. Post-upgrade, verify that both XML
IDs resolve to the same provider record and only that record is enabled.

## Required protected configuration and permissions

Secret values must be supplied through the approved Coolify secret environment:
`ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, and `ENTRA_CLIENT_SECRET`. Never put
their values in Git, screenshots, support tickets, or logs. Also configure
`LHI_ENTRA_MAINTENANCE_ALLOWED_CIDRS` and verify `proxy_mode = True`.

Microsoft application permissions:

- `User.Read.All`: read directory users and managers for app-only provisioning;
- `GroupMember.Read.All`: read approved transitive group memberships.

Interactive delegated permission is `User.Read`, with `openid profile email`.
No mail or directory-write permission is required. This change introduces no new
SharePoint tenant, library, content-type, webhook, or retention requirement.

## Verification evidence

Executed:

```text
python3 -m compileall -q custom-addons/lhi_entra_identity_sync
git diff --check
repository scans for callback overrides, hardcoded provider IDs, manual callback
links, and dashboard registrations
```

Results: Python compilation passed; patch whitespace validation passed; no custom
`/auth_oauth/signin` route, hardcoded provider ID, or manual callback link was
found. The login template uses `auth_link`, and the dashboard component has one
`lhi_dashboard.dashboard_action` registration.

Automated Odoo tests were extended for dry-run creation, silent real-user
provisioning, normalized login, approved baseline access, idempotent repeat sync,
and unchanged `mail.mail` count. They were not executed in this workspace
because Docker Compose stops during interpolation when `POSTGRES_PASSWORD` is
unset and the Odoo Git submodule is not initialized. No test is reported as
passed.

Production-only evidence still required: token acquisition, permission consent,
Graph page/user counts, linked and first-login results, denial cases, local
maintenance login, dashboard/deep links, HTTP 200 for assets and menu loading,
and Coolify restart survival. Record only counts and secret-redacted evidence.

## Deployment and rollback

Before deployment, back up database `lhi_erp` and the filestore, export the
provider configuration, verify two protected local administrators, and record the
current Coolify start command. Use a one-time maintenance command:

```bash
python3 /ACTUAL/PATH/TO/odoo-bin -c /ACTUAL/PATH/TO/odoo.conf -d lhi_erp \
  -u lhi_entra_identity_sync,lhi_web_shell,lhi_dashboard \
  --stop-after-init --no-http
```

Restore the normal long-running Coolify command immediately afterward. Do not use
`-u all`, and do not put `--stop-after-init` or `--no-http` in the permanent
command. The canonical public URL remains `https://work.lhinigeria.org`.

For rollback, disable primary SSO and scheduled/write synchronization, preserve
local administrator access, restore the previous code revision, run the same
one-time update for the three affected modules, and restore provider/system
parameters from the pre-change export. Use run-level rollback only for applied
identity plans whose snapshot drift check passes. Newly provisioned users are
blocked and archived by run rollback; they are not destructively deleted.

## Login and dashboard production repair

The missing Microsoft button was caused by the custom QWeb template filtering the
native `providers` context against `microsoft_provider_id`. That variable
depended on a new external-ID alias which was not guaranteed to exist before the
database module upgrade, so an enabled provider could be silently filtered out.
The template now renders every enabled provider returned by Odoo when it has a
generated `auth_link`, using the native dictionary's `body`, `css_class`,
and `id` values. It displays a secret-safe fallback when no provider is
available. The active custom template remains
`lhi_web_shell.lhi_login_override`, inheriting `web.login`; native provider
context comes from `auth_oauth.providers`, which extends `web.login_oauth`.

The Dashboard crash was caused by changing the JavaScript registry key and server
action tag to `lhi_dashboard.main` while the production database still invoked
the established `lhi_dashboard.dashboard_action` tag. The final canonical tag
is `lhi_dashboard.dashboard_action` in both
`views/dashboard_action.xml` and `static/src/js/lhi_dashboard.js`. The
JavaScript, Owl XML, widget JavaScript, and SCSS remain included once through
`web.assets_backend`. The obsolete, unloaded
`views/dashboard_views.xml` definition was removed.

The scrollbar defect came from a `100vw` by `100vh` wrapper combined with
nested padding and a mobile negative top margin. The login page now uses a
`width: 100%`, `min-height: 100dvh` grid, global page box sizing, bounded
card height, internal scrolling only on short screens, and tablet/mobile
single-column breakpoints.

Static verification covers Python compilation, XML parsing, manifest asset
membership, canonical-tag scans, provider-`auth_link` scans, and
`git diff --check`. Server and QUnit regression tests cover one client action,
menu linkage, registry lookup, obsolete-key absence, native provider fields, and
the `auth_oauth` dependency. Browser viewport checks at 1920×1080, 1600×900,
1440×900, 1366×768, 1280×800, 1024×768, 768×1024, 390×844, and 360×800 require
the upgraded deployed asset bundle and are not reported as passed until executed.

Upgrade only:

```bash
python3 /opt/odoo/odoo-bin -c /tmp/lhi-odoo.conf -d lhi_erp \
  -u lhi_dashboard,lhi_web_shell,lhi_entra_identity_sync \
  --stop-after-init --no-http
```

After the upgrade, verify exactly one `ir.actions.client` whose tag is
`lhi_dashboard.dashboard_action`, and remove only obsolete custom dashboard
actions after confirming that no menu references them. Regenerate only Odoo's
generated `/web/assets/` attachment bundles, restart normally, purge the
Cloudflare cache for `work.lhinigeria.org`, and test local and Microsoft login
in a clean browser session.
