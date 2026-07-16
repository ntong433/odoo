# Sprint 18 Delivery Summary: LHI Asset Management

## Objectives Met
Successfully delivered the standalone `lhi_asset_management` module. It provides a complete, lifecycle-tracked operational asset register independent of Odoo's financial accounting depreciation models, ensuring the logistics team can manage physical custody, maintenance, and disposals safely.

## Models and Features

### 1. Asset Register (`lhi.asset`)
- **Core Tracking**: Manages physical assets via auto-generated `asset_tag` (AST/2026/00001), `serial_number`, and a configurable `lhi.asset.category` matrix.
- **Custody & Ownership**: Maps every asset to a responsible `custodian_id` (Employee/User), a physical `location_id` (HQ, Field, Warehouse, Project Site), and explicitly tracks `donor_id`, `grant_id`, and `project_id` ownership to comply with donor restriction rules.
- **State Machine**: Assets progress logically through `draft` -> `active` -> `maintenance` -> `transfer` -> `disposed`, providing clear visual indicators of the fleet's operational capacity.

### 2. Transfer & Disposal Workflow (`lhi.asset.transfer`)
- **Secure Handovers**: Introduces a dedicated workflow engine for asset movements. A transfer must be submitted and approved before it can be completed. 
- **Multi-Type Logic**: Supports distinct transfer types:
  - **Custody Handover**: Requires a new destination custodian.
  - **Location Move**: Safely transfers the asset to a new facility.
  - **Maintenance**: Flags the asset as temporarily unavailable.
  - **Write-Off / Donation**: Irreversibly removes custody and sets the asset to `disposed`.
- **Automatic Sync**: Upon completing an approved transfer, the destination constraints (new user, new location, or new state) are instantly pushed back onto the core `lhi.asset` record, maintaining a single source of truth while permanently archiving the transfer history.

## Security & Reliability
- **Record Rules**: Assets and their transfer histories are protected by strict `company_id` domain isolation to prevent cross-subsidiary asset bleeding.
- **Automated Testing**: Python tests (`test_asset.py`) rigorously validate that custody handovers legally change the `custodian_id` of the asset, and that write-off/disposal actions correctly strip custody and flag the asset as disposed. All tests pass with 100% compliance.
