# 4. Transition Data Ownership Matrix

Legend: **SoR** = authoritative system of record; **projection** = non-authoritative synchronized copy; **consumer** = uses data without owning it.

| Record/domain | System of record during transition | Other-system responsibility | Conflict rule / key |
|---|---|---|---|
| Organizational user identity, tenant status, immutable user ID | Microsoft Entra ID | Odoo/Leave/OpenSign map identities | Entra wins; immutable `oid` |
| Authentication credentials and MFA | Microsoft Entra ID | Applications hold sessions/service credentials only | Never copy user passwords |
| Organizational directory attributes | Entra ID initially | Odoo stores approved projection; HR validates business fields | Attribute-level contract; `oid` |
| ERP user access roles | New Odoo ERP for business authorization; Entra groups may drive assignments | Entra owns group membership if mapped | Approved mapping + access-review record |
| Employee operational profile | New Odoo ERP after HR validation | Entra provides identity/directory seed; Leave retains its needed profile | Odoo employee external `oid` unique |
| Departments/jobs/work locations | Ownership decision required; proposed Odoo business owner with Entra projection outward | Leave consumes approved values | No dual editing after decision |
| Partners, vendors, donors, customer contacts | New Odoo ERP | Accounting receives approved mappings | Odoo partner external/reference IDs |
| Leads/opportunities | New Odoo ERP | Power BI consumes | Odoo record ID + business reference |
| Projects, tasks, milestones, risks/issues, closeout | New Odoo ERP | Power BI consumes; Accounting receives dimensions if approved | Odoo project code unique |
| Purchase requests, approvals, RFQs and operational POs | New Odoo ERP | Accounting receives controlled reference/status | Odoo request/PO reference; interface ID |
| Vendor bills, journals, payments, tax, GL and financial close | Existing Odoo Enterprise Accounting | New Odoo displays approved references/status only | Enterprise identifiers win pre-cutover |
| Chart of accounts and financial analytic structures | Existing Enterprise Accounting pre-cutover | Odoo operational dimensions mapped explicitly | Signed crosswalk, no implicit matching |
| Products and operational stock | New Odoo ERP | Power BI consumes; Accounting may receive valuation/reference after approval | SKU/company and lot/serial keys |
| Operational equipment/assets and custody | New Odoo ERP | Enterprise owns financial asset/depreciation records | Cross-reference; operational vs financial status separated |
| Vehicles, services, odometers and operational contracts | New Odoo ERP | Power BI consumes; finance receives approved references | Vehicle/tag/VIN governance |
| Leave types, requests, balances, approval steps and leave audit | Existing Leave application | Odoo holds read-only absence projection | Leave request UUID + event version; Leave wins |
| Leave-derived availability/capacity projection | Existing Leave app for fact; Odoo for cached projection | Project planning consumes | Rebuildable projection keyed by leave ID |
| Signature request business intent/link | New Odoo ERP | OpenSign executes ceremony | Odoo signature request UUID |
| Signature ceremony, signer evidence, signed artifact/certificate | OpenSign | Odoo stores verified evidence copy/link | OpenSign document/event ID + document hash |
| Operational audit events | Owning application for native events; Odoo for Odoo business events | Central security platform may aggregate | Event ID, correlation ID, immutable timestamps |
| Operational dashboards | New Odoo ERP for live queues | Power BI not used for transaction control | Source transaction remains authoritative |
| Portfolio/executive semantic model, reports and refresh history | Power BI | Consumes curated Odoo/Accounting data | Dataset version and refresh watermark |
| BI source facts | Originating SoR above | Power BI stores analytical copies | Source IDs retained; no write-back |

## Ownership governance

- Every interface field must have one named data owner and one authoritative edit path.
- Projections are visibly read-only and carry source system, external ID, source update time and last successful synchronization time.
- Merge rules must never rely on mutable email address alone; use Entra `oid` for people and agreed stable business keys for other domains.
- Deletion from a source becomes an explicit tombstone/archive event where audit or relational integrity requires retention.
- Data-quality exceptions have a queue, accountable owner, SLA and reconciliation report.

