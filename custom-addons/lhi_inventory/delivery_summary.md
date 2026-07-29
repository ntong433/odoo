# Sprint 18 Delivery Summary: LHI Inventory Configuration

## 2026-07-29 Odoo 19 safety correction

The no-op `_update_available_quantity` override and the post-move quant stamping
override were removed. The former did not match the Odoo 19 positional
`reserved_quantity` signature; the latter could select the wrong quant because
package, owner, company, and other quant identity dimensions were absent.
Project and donor references remain on stock moves, pickings, and move lines.
Any balance attribution will be implemented through controlled HUB transaction
and consignment ledgers rather than mutation of an ambiguous quant.

The manifest no longer depends on `lhi_purchase_order`; it declares the actual
`lhi_project_workplan` dependency used by `lhi_activity_id`. This removes the
unintended Accounting dependency path.

## Objectives Met
Successfully implemented the `lhi_inventory` module to configure Odoo's native stock module for LHI's operational requirements, explicitly disabling automated accounting valuation while introducing structural tracking for organizational projects and donors.

## Models and Features

### 1. Stock Extensions (`lhi_stock_inherit.py`)
- **Stock Move (`stock.move`)**: Extended to include `lhi_project_id` (Project Allocation) and `lhi_donor_id` (Donor Ownership). This ensures that every movement of goods (receipt, issue, transfer, return) is legally and operationally stamped with funding metadata.
- **Stock Quant (`stock.quant`)**: Legacy project/donor fields remain available
  for compatibility, but are no longer populated by unsafe first-match mutation.

### 2. Operational Workflows
- **Warehouses & Field Stores**: By inheriting Odoo's native stock module without the `account` module dependency, LHI now securely manages central warehouses, field-office stores, and project site locations.
- **Transfers & Issues**: End-to-end support for stock receipts from procurement, internal transfers across offices, stock issuance to activities, and physical stock counts (adjustments).

## Security & Reliability
- **Multi-Company Operations**: Stock locations, moves, and quants inherently respect Odoo's standard multi-company access-control structures.
- **Automated Testing**: Executed the native test suite and added specific `test_inventory.py` logic. Confirmed that validating a receipt properly cascades project and donor tags from the stock move down to the finalized stock move line, keeping tracking completely intact from procurement to storage.
