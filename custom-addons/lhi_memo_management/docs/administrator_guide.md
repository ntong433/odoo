# Memo administration

## Prerequisites

- Keep the existing Microsoft Entra tenant as the identity provider.
- Keep Odoo RBAC authoritative. Entra mappings must not manage Memo
  Administrator, Signature Preparation Officer, or Signature Administrator.
- Retain the existing ERP SharePoint site, Documents drive, ERP root, storage
  policies, and Graph connection.
- Grant the runtime Entra application Microsoft Graph `Sites.Selected`
  application permission and explicit `write` permission only on the approved
  ERP site. Do not grant tenant-wide `Files.ReadWrite.All` or
  `Sites.ReadWrite.All`.
- Configure delegated `Sites.Selected` with `openid`, `profile`, and
  `offline_access` only where the existing Microsoft integration requires user
  interaction.
- Configure OpenSign against the same Entra tenant so it establishes its own
  authenticated session. An Odoo cookie is not an OpenSign session.

## LHI Sign provider configuration

As a Signature Administrator, open **Signature Administration →
Configuration** and create one active record per company:

- API base URL, including the supported OpenSign API version path;
- allowed preparation/signing hosts;
- allowed signed-artifact download hosts;
- bounded timeout, retry, backoff, and artifact-size settings.

Store secret values in protected Coolify environment variables:

```text
LHI_OPENSIGN_API_TOKEN
LHI_OPENSIGN_WEBHOOK_SECRET
```

If environment injection is unavailable, use the access-restricted Odoo system
parameters named by the configuration record. Never put secret values in the
record, URLs, source, logs, or browser storage.

Configure the provider webhook to call:

```text
https://work.lhinigeria.org/api/opensign/callback
```

The callback requires an HMAC-SHA256 hexadecimal signature in
`x-webhook-signature`, calculated over the exact raw request body.

## Memo categories and routes

Under **Memos → Configuration → Memo Categories**, configure the company,
default recipients, expiry, requester/final signature requirements, optional
approved Word starter, and an active memo approval matrix. Starters control
layout only; every signature field is placed dynamically on the captured PDF.
An explicitly selected route must match the memo company, currency, amount,
department, office, project, and grant restrictions. If a category does not
select a route, the existing approval engine resolves the matching matrix.

Each `any` memo stage must resolve to one person. The final signature stage
must resolve to exactly one final authority. Each participant must have a
synchronized Entra tenant ID, immutable object ID, and UPN/email.

## Roles

- Memo User: own/addressed memos.
- Memo Approver: assigned memo decisions.
- Department Memo Manager: configured department scope.
- Records Officer: approved record scope.
- Memo Administrator: categories and memo governance, not provider secrets.
- Signature Preparation Officer: only explicitly assigned preparation work.
- Signature Administrator: provider requests, failures, webhooks,
  reconciliation, and configuration.

Do not grant Settings administrator rights as a shortcut.

## Diagnostics and recovery

Use Signature Administration to inspect failed requests and webhook events.
Use **Reconcile** only for provider requests with a known provider ID. If draft
creation reports an uncertain outcome, investigate the provider before retrying
so a second envelope is not created. After confirming that no provider document
exists, a Signature Administrator may use **Reset Uncertain Draft** and retry;
the reset is recorded in chatter. SharePoint failures retain bounded spool data
and an idempotent integration job; the memo remains failed/non-completed until
immutable DriveItem IDs are confirmed.
