# ADR-0001: Custom Addons and Core Boundary

- Status: Proposed
- Date: 2026-07-15

## Context

LHI requires upgrade-safe Odoo 19 Community extensions. A prototype currently exists under `odoo/addons`, and core divergence would increase upgrade and security risk.

## Decision

All LHI code will live in workspace `custom-addons/`, use `lhi_` namespacing and extend Odoo through supported inheritance, registries, assets, controllers and hooks. Core changes require proof that no extension exists, a documented exception and approval.

## Consequences

CI must load both core and custom addon paths. Existing prototypes require reviewed migration. Adapter modules will isolate cross-domain dependencies. Install and upgrade tests become release gates.

