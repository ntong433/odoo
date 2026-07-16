# Entra and SharePoint security configuration

## Entra application

Tenant ID:

`552a1d00-ce70-4fdb-940f-0ad131e4b9cb`

Application/client ID:

`02b3748f-e84b-4bec-935a-21fab1498517`

Register both production web redirect URIs exactly:

- primary Odoo sign-in:
  `https://work.lhinigeria.org/auth_oauth/signin`
- delegated Microsoft Graph code/PKCE:
  `https://work.lhinigeria.org/lhi/microsoft_graph/oauth/callback`

Application-only authentication uses the OAuth 2.0 client-credentials flow with
the protected `ENTRA_CLIENT_SECRET` value. Do not use the Coolify/Traefik TLS
certificate for Microsoft Graph.

## Required Microsoft Graph permissions

| Context | Permission | Type | Purpose |
|---|---|---|---|
| Application | `Sites.Selected` | Application | Background SharePoint document operations |
| Application | `User.Read.All` | Application | Approved Entra identity synchronization |
| Application | `GroupMember.Read.All` | Application | Approved nested group-membership synchronization |
| Delegated | `Sites.Selected` | Delegated | User-driven SharePoint and Office operations |
| Delegated | `openid` | OIDC | User sign-in |
| Delegated | `profile` | OIDC | Basic signed-in user claims |
| Delegated | `email` | OIDC | Controlled initial identity matching |
| Delegated | `offline_access` | OIDC | Delegated token renewal |
| Delegated | `User.Read` | Delegated | Signed-in user identity |

Do not grant tenant-wide application file/site permissions while
`Sites.Selected` satisfies the SharePoint requirement. Entra directory
permissions are tenant-level by Microsoft design, so Odoo limits processing to
approved users and mapped group IDs.

Administrator consent alone does not grant SharePoint resource access. Retain
the explicit `write` assignment for this client ID on the approved ERP site.

## Confirmed SharePoint resources

- Hostname: `lhisokoto.sharepoint.com`
- Site path: `/sites/ERP`
- Site ID:
  `lhisokoto.sharepoint.com,a307baa8-0966-493a-8c93-147ab14d086d,88f486b7-3c86-436f-a0de-0968fbf2d420`
- Document library: `Documents`
- Drive ID:
  `b!qLoHo2YJOkmMkxR6sU0IbbeG9IiGPG9DoN4JaPvy1CAv6wvCWH9ZQIOHqh5ZXKtf`
- ERP root folder: `ERP`
- ERP root DriveItem ID: `01QTWNMA2W4O2DS5DA5VBIK7ARAKQREBQT`

Logical storage roles remain Projects, Procurement, Operations, Controlled
Documents, and Signed Documents. They map into governed folders below the same
validated `Documents/ERP` root and continue to use immutable DriveItem IDs.

## Security boundaries

- Existing `lhi_security`, record rules, project assignments, approval
  matrices, and SoD rules remain authoritative.
- Entra group synchronization maps only to existing Odoo groups.
- Protected local administrators are excluded from automatic identity changes.
- Delegated actions cannot exceed the signed-in user's SharePoint permissions.
- Application credentials cannot impersonate users or create anonymous links.
- No client secret, token, authorization header, or webhook client-state value
  may be stored in source control or diagnostic output.

## Selected-site assignment

Run `provisioning/Grant-LhiSitesSelected.ps1` from an approved administrator
workstation:

```powershell
./Grant-LhiSitesSelected.ps1 `
  -SiteId "lhisokoto.sharepoint.com,a307baa8-0966-493a-8c93-147ab14d086d,88f486b7-3c86-436f-a0de-0968fbf2d420" `
  -ApplicationClientId "02b3748f-e84b-4bec-935a-21fab1498517" `
  -Role write `
  -WhatIf
```

Review the output before removing `-WhatIf`.
