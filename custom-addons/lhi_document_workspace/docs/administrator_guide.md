# Administrator guide

## Prerequisites

Before installing this module:

1. Configure and validate `lhi_microsoft_graph_core`.
2. Install and validate `lhi_sharepoint_storage`.
3. Confirm delegated Microsoft authorization works for staging users.
4. Confirm the approved SharePoint site and its Projects, Procurement,
   Operations, Controlled Documents, and Signed Documents libraries are valid.
5. Enable SharePoint versioning and recycle-bin behavior.
6. Confirm users have both the required Odoo business access and the
   corresponding SharePoint resource access.

The production Odoo URL and Entra redirect URL remain:

`https://work.lhinigeria.org`

`https://work.lhinigeria.org/lhi/microsoft_graph/oauth/callback`

## Authorization design

The server always verifies the current user's access to the linked Odoo
business record before returning metadata or initiating a Microsoft action.
Project-scope results are re-evaluated under the current user so existing
record rules remain effective.

Interactive preview, edit, version, template creation, download, and archive
operations use delegated Graph access for the actual Odoo user. SharePoint
therefore authenticates the Entra user and applies its resource permissions.
The module does not create anonymous sharing links and does not expose Graph
access tokens to browser JavaScript.

Application access is used only by the existing storage foundation and by an
ERP administrator validating a configured template source. It remains limited
to the selected LHI ERP SharePoint resource.

## Menus

ERP administrators use:

- Integration → Configuration → Microsoft Graph → Office Document Templates
- Integration → Configuration → Microsoft Graph → Document Storage Policies
- Integration → Monitoring → SharePoint Documents
- Integration → Monitoring → Graph Request Logs
- Integration → Monitoring → Integration Jobs

Internal auditors have read-only access to Office template configuration.
Ordinary users do not receive direct ACL access to `lhi.document.template` or
`lhi.document.item`; they use the workspace on an authorized business record.

## Storage policies

Each supported document model requires a SharePoint storage policy with
**Workspace Enabled** selected. Disabling this field removes policy-backed
documents from workspace queries and blocks workspace preview/version routes.

`Workspace Lock States` is a comma-separated list of linked-record states that
block edit, desktop open, new-version, replacement, and archive actions.
Preview, version history, governed link, and download remain read operations.

The default lock states are:

`locked,done,cancel,cancelled,closed,completed,signed,archived`

The module also respects explicit Boolean lock fields named
`lhi_document_locked`, `document_locked`, `is_locked`, or `locked` when a
business model provides one.

Change lock states only after testing the affected workflow and approval
controls. UI button visibility is not the security control; server-side linked
record access and lock checks remain mandatory.

## Approved Office templates

Templates are existing Word, Excel, or PowerPoint files in an approved
SharePoint library. To configure one:

1. Open **Office Document Templates**.
2. Select the company and validated Graph connection.
3. Enter the exact target Odoo model, such as `lhi.project` or
   `lhi.project.report`.
4. Select Word, Excel, or PowerPoint.
5. Enter the protected source Drive ID and immutable DriveItem ID.
6. Select **Validate and Approve**.

Validation reads the source with application access, verifies that it is a
file, records its name, MIME type, size, and validation identity, and checks
that its extension matches the selected Office type.

When a user creates a document, the module:

1. verifies write access to the current Odoo record;
2. checks the approved model- and company-scoped template;
3. downloads the source through that user's delegated Microsoft context;
4. validates the target filename and storage policy;
5. uploads to the policy-selected SharePoint folder;
6. verifies the returned immutable DriveItem ID and metadata;
7. marks the document available only after verification; and
8. returns the authenticated SharePoint `webUrl` for Microsoft 365 editing.

Template bytes are held only in process memory for the bounded small-file
operation. They are not written to the Odoo filestore.

## Preview and editing

The default document click loads the Odoo preview controller in an iframe. The
controller rechecks linked-record read access and requests a fresh, short-lived
Microsoft Graph preview URL. Unsafe or missing preview URLs fail closed.

**Edit in Microsoft 365** synchronously opens a blank browser tab from the user
click, then verifies Odoo write access and workflow state before navigating the
new tab to the current authenticated SharePoint web URL with `web=1`.

If the browser blocks the new tab, the action stops without replacing the
original Odoo record or creating a template-derived file.

When the Odoo tab regains focus, metadata is refreshed by immutable DriveItem
ID. A changed ETag produces a non-blocking newer-version notification.

## Version upload and retry behavior

New-version and replacement actions create a delegated upload session for the
existing immutable DriveItem and use its current ETag as a precondition.
Browser chunks are sequential and use the policy's configured chunk size.

Transient network failures and HTTP 429/500/502/503/504 responses are retried
up to five times with bounded exponential backoff. `Retry-After` is honored up
to 60 seconds. Each browser request has a two-minute timeout.

Odoo accepts completion only when:

- the upload session is still active;
- SharePoint returns the same immutable item ID;
- the ETag changed;
- the file is non-empty and satisfies the policy;
- remote hashes and metadata can be refreshed; and
- the DriveItem verification succeeds.

## Diagnostics and operations

Use the existing Graph request logs and integration diagnostics for redacted
request status, throttling, correlation identifiers, and delegated
authorization failures. Workspace actions also create `lhi.audit.log` events
for preview, edit, download, version changes, archive, template creation, and
governed-link copy.

Common checks:

- a missing workspace tab: verify module/view installation;
- an empty list: verify linked metadata, policy enablement, company, project
  scope, and the user's record rules;
- preview failure: verify delegated authorization and iframe/CSP policy;
- edit failure: verify write ACL/record rule, workflow state, delegated access,
  and SharePoint permission;
- stale metadata: refocus the Odoo tab or use Refresh;
- version failure: inspect upload-session expiry, ETag conflict, policy size
  and extension limits, and Graph throttling logs.

Do not repair a workspace issue by granting Odoo technical administration,
tenant-wide Graph permissions, anonymous SharePoint links, or permanent local
file storage.
