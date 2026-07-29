# Administrator configuration

## Installation prerequisites

Install or upgrade the declared dependencies before `lhi_hub_management`.
The critical reused services are:

- `lhi_approval_matrix` for configurable route selection and immutable route
  snapshots;
- `lhi_signature_bridge` for LHI Sign provider preparation, protected signing
  URLs, authenticated webhook processing, reconciliation, final PDF, and audit
  certificate capture;
- `lhi_sharepoint_storage` for fail-closed business-document storage;
- `lhi_security` for operational roles;
- `lhi_asset_management` for serial-to-asset promotion; and
- `lhi_inventory` for project/donor/activity stock provenance.

Do not install Accounting, `stock_account`, Sales, Rental, or HR as a
prerequisite.

## HUB setup

1. Open **Operations → Configuration → HUBs and Locations**.
2. Complete State, Office, Operations Manager, Warehouse Officers, Operations
   Officers, and Authorized Users.
3. Every assigned officer/manager must also be in Authorized Users.
4. Use **Create Standard HUB Locations**. Review the generated Receiving, NFI,
   Medical, Pharmaceutical, Consumables, Quarantine, Damaged, Dispatch, Lease,
   and Returns areas.
5. Confirm receipt, dispatch, quarantine, damaged, returns, and lease defaults.
6. Assign each user only the required HUBs on the user's **Authorized HUBs**
   page.

Existing lots are assigned a controlling HUB by the post-migration script when
their current internal location resolves to a HUB. Resolve unassigned legacy
lots before allowing officers to transact with them.

## Products and pharmaceuticals

Use the protected top-level categories and create configurable subcategories.
For each HUB product:

- enable storable inventory;
- select the HUB item type;
- select a tracking method;
- require lots and expiration for Pharmaceuticals;
- require serial tracking for individually identifiable or leaseable
  equipment;
- configure the operational value source, value date, and currency;
- configure low-stock threshold where used; and
- configure Asset Category only if the serial may be promoted to the Asset
  Register.

The Pharmaceuticals category uses FEFO. Quarantined, rejected, expired, or
removal-date stock is blocked at the server boundary.

## Approval matrices

Create matrices with document type **HUB Stock Request**. Configure requested
value, total requested quantity, HUB, state, inter-state, product/category,
project, programme, grant/award, donor/partner, priority, emergency, effective
dates, pharmaceutical, controlled-item, restricted-consignment, and serialised
equipment criteria as needed. Value thresholds deliberately use the requested
value when the route is selected; approved-value totals are established only
after quantity review.

Every stage resolves active `res.users` and snapshots:

- sequence, role, security group, eligible users, approval type, delegation,
  and escalation data;
- whether LHI Sign is required; and
- the exact signer name/email/Entra identity.

Signature stages must resolve exactly one signer with an email and synchronized
Entra object ID. Non-signature stages must precede signature stages. When NED
is present, Director of Operations must occur first. Later matrix edits do not
alter a submitted route.

## LHI Sign and SharePoint

Reuse the existing connections; do not create another provider connection.
Configure signature templates/coordinates in LHI Sign preparation. Every
participant requires Signature, Name, and Date widgets. The bridge blocks
activation if required widgets are absent.

The addon installs SharePoint policies for:

- consignment evidence;
- request evidence;
- request source, signed PDF, and audit certificate;
- dispatch/receipt artifacts;
- external-recipient evidence;
- external issue evidence; and
- equipment lease evidence.

Map the policy library codes (`operations`, `controlled_documents`, and
`signed_documents`) to approved SharePoint libraries. Business uploads are
synchronous and fail closed. Keep the SharePoint connection, drive/site IDs,
client secret/certificate, webhook secret, and provider credentials in the
existing restricted settings/secret store—never in Git.

Required Microsoft permissions are inherited from the existing integrations;
this addon introduces no new Entra or Graph permission. The existing
least-privilege SharePoint/Graph application still needs only the site/library
and webhook permissions documented by `lhi_sharepoint_storage` and
`lhi_signature_bridge`.

## Notifications

The queue always attempts an in-system activity. If an Odoo outbound mail
server exists and the recipient has an email, it also queues `mail.mail`.
Missing SMTP/Graph mail transport produces **No Outbound Email Transport** and
does not roll back the business transaction. Configure one approved transport
and use **Notification Diagnostics → Resend** for retained events.

LHI ERP sends workflow context. LHI Sign owns protected signing-link messages;
do not configure duplicate signing-link emails.

Set the non-secret system parameter `lhi_hub.expiry_alert_days` to the desired
pharmaceutical warning window. The default is 90 days; runtime handling is
bounded to 1–365 days. Low-stock recipients come from the HUB's Operations
Manager, Warehouse Officers, and Operations Officers. Thresholds are configured
on each HUB product.

## Payment methods

Review Cash, Bank Transfer, POS, Mobile Money, and Other. References are
required except for Cash by default. These records produce operational revenue
only—never invoices, payments, journal entries, or receivables.

## Stock adjustments

Stock adjustments are a separate Operations Management permission. They are
not enabled for Programme Users, Warehouse Officers, or Operations Officers.
Before use, confirm every company has an Inventory Loss location configured on
storable products. Every adjustment requires an assigned HUB, exact internal
storage location, operational reason, and non-zero line delta. Tracked items
require a lot/serial; a serial delta must be exactly one unit.

Validated adjustments are immutable inventory moves. Corrections use the
reason-required reversal action, never direct quant edits or deletion.

## Scheduled actions

- notification delivery: every five minutes, bounded to 100 records;
- overdue lease detection: daily, bounded to 200 leases; and
- stock and pharmaceutical-expiry alert queuing: daily, bounded to 200 HUBs,
  500 threshold-controlled products, and 500 expiring lots.

All are idempotent. Review cron ownership, allowed companies, backlog, and
failure diagnostics after installation.
