# User workflows

## Consignments

Create the consignment, identify donor/partner restrictions, and enter expected
lines. Submit, mark expected, record physical receipt, inspect accepted/rejected
quantities, and record discrepancies. **Post Accepted Stock** creates and
validates an incoming picking; direct quant edits are not used. Close only
after posting.

Pharmaceutical lines require a batch and future expiry date. The resulting lot
retains donor, project, award, consignment, and controlling-HUB provenance.

## Internal HUB stock request

1. A Programme User or Operations Officer creates a request for an assigned
   requesting HUB and selects a valid matrix.
2. Submission snapshots the route. It does not reserve or move stock.
3. Authorized supplying-HUB officers refresh availability and record
   recommended/approved quantities, valid lots, alternatives, remarks, and
   partial-fulfilment reasons.
4. Locking validates availability, freezes quantities, renders one immutable
   PDF, hashes it, stores it in SharePoint, and creates one idempotent LHI Sign
   request.
5. An authorized preparer places/validates all Signature, Name, and Date
   widgets before signing begins.
6. The current approver uses **Approve and Sign**. Opening the protected URL
   never approves the stage. Only an authenticated provider event or explicit
   reconciliation for the expected participant advances it.
7. After every required signature, the bridge verifies and stores the final
   PDF and certificate in SharePoint. Only then is **Reserve Stock** available.
8. Officers may dispatch and receive partial quantities. The system uses
   transit pickings, retains outstanding balances, and stores dispatch/receipt
   PDF artifacts in SharePoint.
9. A partial balance can close only with an unfulfilled-balance reason.

Return/rejection requires a reason and revokes/supersedes the active signature
request. A correction increments the document version and restarts the full
route. Withdrawal is requester/Operations-management only and never moves
stock.

## External issues and distributions

External recipients are `res.partner` records and need no login, Entra account,
employee record, or internal role. Capture only necessary identity/contact and
consent references.

Select an assigned HUB, recipient, transaction basis, products, quantities,
valid lots/serials, and operational collection data. Mass distributions may
use structured recipient records or a SharePoint-backed beneficiary list and a
bounded beneficiary count. Validation immediately creates a real stock issue.
There is no approval matrix and no LHI Sign route.

Validated transactions are immutable. Management enters a reversal reason and
uses **Create Stock Reversal**, which creates a linked incoming movement and a
negative operational-revenue record where applicable.

## Equipment leases

Warehouse/Operations Officers—not a separate Lease Officer—select serialised,
leaseable equipment. Record charging basis, rates, terms, payment or authorized
waiver, and release condition. Release is blocked for unavailable, quarantined,
expired, or already leased serials and uses a validated outgoing picking.

Record return condition, damage and late charges, then receive through an
incoming picking. Post operational payments separately. Posted payments are
immutable; management records a reason and creates an auditable negative
reversal. Close only when equipment is returned and the operational balance is
settled or waived.

## Stock adjustments

Operations Managers use **Operations → Stock Adjustments** only after a
physical count or documented operational correction. Select the assigned HUB
and exact storage location, write a clear reason, and enter positive deltas for
additions or negative deltas for removals. Validation captures quantities
before/after and creates an inventory movement carrying the adjustment
reference and reason.

Validated adjustments cannot be edited or deleted. Enter a reversal reason and
use **Create Reversal** to correct one; this produces a linked opposite
movement and retains both records.

## Dashboard

Cards and chart segments open filtered lists. Results use the current user's
company and record rules. If one source is inaccessible or temporarily fails,
that widget is omitted with a controlled warning; the remaining dashboard and
navigation continue loading.
