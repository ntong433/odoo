# ADR-0006: Power BI Analytics Boundary

- Status: Proposed
- Date: 2026-07-15

## Context

Portfolio and executive analytics need cross-domain history without placing analytical load or write-back risk on Odoo transactions.

## Decision

Power BI owns semantic models, executive reports and refresh history. It consumes versioned, curated, read-only datasets from Odoo and Enterprise Accounting. Odoo remains authoritative for operational facts; Power BI never writes business state back.

## Consequences

Dataset contracts require lineage, watermarks, reconciliation, field allowlists, privacy review and row-level security. A curated analytics store/read replica is preferred over unrestricted direct transactional database access.
