# Administrator guide

## Authentication boundaries

The integration uses three separate security contexts:

- primary Odoo sign-in returns to
  `https://work.lhinigeria.org/auth_oauth/signin`;
- delegated Microsoft Graph authorization-code/PKCE returns to
  `https://work.lhinigeria.org/lhi/microsoft_graph/oauth/callback`;
- background Microsoft Graph and SharePoint operations use the OAuth 2.0
  client-credentials flow with `ENTRA_CLIENT_SECRET`.

The application secret is read only from the process environment. It is never
stored in an Odoo field, exposed through an Odoo configuration API, sent to
browser JavaScript, or included in an authorization URL.

## Prerequisites

1. Configure both redirect URIs exactly in the Entra application registration.
2. Grant the application permissions approved for SharePoint and identity sync.
3. Keep `Sites.Selected` and assign this application `write` access only to the
   approved ERP SharePoint site.
4. Configure the confirmed site, drive, and root DriveItem identifiers in
   protected Coolify environment settings.
5. Set Odoo's production base URL to `https://work.lhinigeria.org`.
6. Keep the protected local maintenance administrator route operational.

## Odoo configuration

Open **Integration → Configuration → Microsoft Graph → Connections** as an LHI
ERP Administrator.

Create one active connection per company. Tenant, client, site, drive, and root
reference fields may be populated for administrator visibility, but runtime
authentication and resource selection use the protected environment contract.

Retain:

- application permission mode: `Sites.Selected`;
- delegated permission mode: `Sites.Selected`;
- delegated scopes: `openid profile offline_access Sites.Selected`;
- SharePoint hostname: `lhisokoto.sharepoint.com`;
- site path: `/sites/ERP`.

Select **Validate Site**, then **Validate Libraries**. Every logical library role
is validated against the same `Documents` drive and the immutable `ERP` root
DriveItem. Odoo stores only the identifiers Graph confirms.

## Delegated user authorization

Each user opens Preferences and selects **Authorize Microsoft 365**. The
authorization URL uses code flow with PKCE and an expiring signed state tied to
the Odoo database and user. The client secret never appears in the browser URL.

Preview and edit actions continue to use the actual signed-in Microsoft user.
The application token cannot impersonate a user or create anonymous links.

## Diagnostics

Use **Integration → Monitoring → Graph Diagnostics** or **Run Diagnostics** on a
connection. Safe diagnostics report:

- tenant configured: yes/no;
- client ID configured: yes/no;
- client secret configured: yes/no;
- token acquisition success/failure;
- token expiry time;
- Graph request ID; and
- SharePoint site, drive, and ERP root validation success/failure.

Secret length, token payloads, access tokens, refresh tokens, authorization
headers, client secrets, and webhook client-state values are excluded.

Use **Clear App Token Cache** after client-secret rotation. The next background
Graph operation obtains a token using the current protected Coolify secret.

## Failure behavior

Token or Graph failure does not disable Odoo login, remove synchronized roles,
or create permanent local document fallback. Existing local RBAC and the last
successfully synchronized authorization state remain authoritative.

The daily cleanup job removes expired/reused delegated OAuth states and old
request logs in bounded batches. Application tokens expire naturally or can be
cleared explicitly during rotation.
