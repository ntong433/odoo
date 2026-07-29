# Security and control design

## Role boundary

- HUB Viewer: read assigned HUB data.
- Warehouse Officer / Operations Officer: execute governed stock workflows in
  assigned HUBs.
- Operations Manager: supervise assigned HUBs, configuration, reason-controlled
  stock adjustments/reversals, and matrix stages.
- Director of Operations: organization-wide Operations visibility and
  configured signature stages.
- NED / Programme Approver: only requests frozen into their approval route.
- Programme User: own stock requests for assigned requesting HUBs; no stock
  mutation.
- System Auditor: company-wide read-only operational and audit data.
- LHI ERP Administrator: technical recovery/configuration, including Inventory
  administration.

No role requires `hr.employee`. No general approver receives Signature or
Integration Administrator access.

## Server-enforced invariants

- company-global record rules intersect assigned-HUB rules;
- stock locations expose only assigned internal locations plus the supplier,
  customer, and transit boundaries required by workflows;
- lot/serial access uses durable controlling-HUB provenance;
- source transaction IDs on pickings/moves are workflow-generated and
  immutable;
- workflow-only context values use a process-local sentinel that JSON/RPC
  callers cannot forge;
- stock is changed only by confirmed/validated pickings;
- reservation checks availability under row-locking/reservation semantics and
  cancels safely on shortage;
- expired/quarantined stock is blocked on lot validation and move lines;
- serial leases use row locking and active-lease duplicate checks;
- stock adjustments require Operations Management, a reason, a retained
  inventory movement, and a transaction-scoped advisory lock preventing
  concurrent negative deltas;
- validated issues, revenue, request versions, and report artifacts are
  immutable;
- approval routes authorize only users in the submitted request-line snapshot;
- mutable matrix configuration is never consulted for a submitted decision;
- requester segregation of duties is enforced by the approval engine;
- generic approval RPC actions cannot decide HUB requests;
- approval completion requires a matching current signer from an authenticated
  provider event;
- stock reservation requires final provider completion plus verified
  SharePoint signed PDF and certificate;
- provider URLs remain in restricted integration models and are returned only
  after current-participant authorization; and
- notification and provider idempotency keys prevent duplicates.

Notification hooks cover request submission/review/signing/approval,
rejection/return/withdrawal, reservation readiness, dispatch/receipt/partial
fulfilment, consignment discrepancies, low stock, pharmaceutical expiry,
overdue and outstanding leases, asset assignment/transfer/disposal, and
integration failure. Workflow-context messages never contain provider signing
links; LHI Sign remains responsible for those.

Internal recipients can read and resend only their own queue entries.
Operations Management and auditors retain company-wide diagnostics. No user
group has notification-create permission; only workflow code holding the
process-local token can create delivery records.

The dashboard deliberately does not use `sudo()` for business metrics. Narrow
`sudo()` is limited to notification queue insertion/delivery and bounded alert
scanning, immutable provider/document metadata, webhook-owned state, and HUB
provenance updates after an authorized stock movement has validated. It is not
used to authorize business workflow decisions or dashboard metrics.

## Data privacy

External recipients need only operational contact, recipient classification,
location, programme context, and optional consent/evidence references.
Identification bytes and beneficiary lists belong in SharePoint, not free-text
database fields. Record rules limit transactions to assigned HUB staff and
authorized management/auditors.
