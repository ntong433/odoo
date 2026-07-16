# ADR-0003: Existing Leave Remains System of Record

- Status: Proposed
- Date: 2026-07-15

## Context

The existing Leave application already implements Entra-linked requests, balances, sequential approvals, notifications and audit data. Rebuilding would create dual ownership and migration risk.

## Decision

Leave remains authoritative for leave types, requests, balances, approvals and leave audit. Odoo holds a read-only, rebuildable absence projection for planning and display through a versioned API/event contract keyed by Leave request ID and Entra object ID.

## Consequences

Odoo cannot approve leave or adjust balances. Leave wins conflicts. The connector must reconcile duplicates, missing/out-of-order events and employee mappings. Standard `hr_holidays` must not become a parallel production ledger.

