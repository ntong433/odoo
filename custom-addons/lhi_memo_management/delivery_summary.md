# Delivery summary

## Scope and versions

- New: `lhi_memo_management` `19.0.1.0.0`.
- `lhi_approval_matrix`: `19.0.1.0.1` → `19.0.1.0.2`.
- `lhi_signature_bridge`: `19.0.1.0.0` → `19.0.1.0.1`.
- `lhi_dashboard`: `19.0.1.3.9` → `19.0.1.3.10`.
- `lhi_web_shell`: `19.0.1.1.4` → `19.0.1.1.5`.
- No Odoo core module is changed.

## Data model and migrations

The delivery adds `lhi.memo`, `lhi.memo.category`, and
`lhi.memo.approver.line`; extends approval document types with `memo`; and adds
structured signature recipient, provider configuration, and idempotent webhook
event models. Existing generic signature requests, resource links, provider
IDs, binaries, hashes, and certificates are preserved. New document payloads
are routed to SharePoint and cleared/not written to Odoo binary columns.

The signature bridge includes an additive ORM post-migration that derives the
company on historical requests from the unchanged source relationship or
provider configuration. It does not delete or rewrite provider IDs, resource
links, hashes, signed PDFs, certificates, or webhook history. Existing
signature ACL XML IDs are updated in place to the protected Signature
Administrator group. A pre-deployment backup is mandatory.

## Security and integrations

Server-side record rules enforce company, ownership, participant, department,
records, and administrator scopes. Protected signature roles cannot be managed
by Entra synchronization. Provider redirects and artifact URLs require HTTPS
and configured host allowlists. Provider webhook payloads require raw-body
HMAC-SHA256, stable event IDs, unique constraints, safe retry, and restricted
raw payload access. Local participant/approval changes use savepoints so a
failed event cannot leave a half-advanced route. Completion artefact records
remain durable across retries so a successful remote SharePoint upload is not
orphaned by a later local failure.

New secret-store names (values never committed):

- `LHI_OPENSIGN_API_TOKEN`
- `LHI_OPENSIGN_WEBHOOK_SECRET`

Required Graph permission remains `Sites.Selected`, with an explicit
site-specific write grant to the existing ERP site. No new SharePoint tenant,
site, library, content type, retention label, or broad Graph permission is
required. Existing controlled-document retention configuration applies.

## Deferred runtime evidence

Python compilation, linting, XML parsing/RelaxNG, manifest imports, and Odoo
JavaScript transpilation are recorded during delivery. Full Odoo registry,
view, asset-bundle, and transactional test execution plus disposable database
exit codes require the production-like container because this workstation has
no reachable PostgreSQL service. Production installation and browser workflow
testing are deliberately not performed from the development workspace. The
deployment guide names the exact targeted commands and checks.

The local targeted command reached Odoo 19 and exited `1` before registry
creation because `/var/run/postgresql/.s.PGSQL.5432` does not exist. Docker
could not supply PostgreSQL because this user cannot access
`/var/run/docker.sock`. This is environmental—not a passed disposable test—so
deployment remains gated on the documented container command exiting `0`.
