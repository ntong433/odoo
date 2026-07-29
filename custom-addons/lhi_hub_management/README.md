# LHI HUB Management

Operational stock management for LHI ERP on Odoo 19 Community.

This addon extends Odoo Inventory's technical models and presents them as the
LHI HUB workspace. It does not depend on HR, Accounting, Invoicing, Sales,
Rental, or `stock_account`, and it never creates accounting records.

## Scope

- assigned-HUB access on warehouses, locations, quants, pickings, moves,
  lots/serials, and LHI operational documents;
- protected NFI, Medical Equipment, Consumables, and Pharmaceuticals
  categories;
- operational stock valuation without accounting valuation;
- donor/partner consignment receiving through validated stock pickings;
- internal HUB requests with immutable quantity snapshots, the existing
  approval matrix, one sequential LHI Sign document, provider-confirmed
  decisions, SharePoint document storage, reservation, partial dispatch, and
  partial receipt;
- direct external issues, sales, free/programme distributions, returns, and
  auditable reversals without approval or LHI Sign;
- serial-controlled equipment leases, operational collections, damage/late
  charges, waivers, returns, and payment reversals;
- reason-controlled stock adjustments restricted to Operations Management,
  with concurrent negative-stock protection and reversing movements;
- centralized, deduplicated workflow notifications plus daily low-stock and
  pharmaceutical-expiry alerts;
- a permission-aware HUB dashboard whose sources fail independently; and
- links between serialised stock and the operational Asset Register.

See [administrator configuration](docs/ADMIN_CONFIGURATION.md),
[user workflows](docs/USER_GUIDE.md), [security controls](docs/SECURITY_AND_CONTROLS.md),
and [deployment and rollback](docs/DEPLOYMENT_AND_ROLLBACK.md).

No demo or production placeholder business data is loaded.
