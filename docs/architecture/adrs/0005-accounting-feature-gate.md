# ADR-0005: Accounting Transition and Feature Gate

- Status: Proposed
- Date: 2026-07-15

## Context

Existing Odoo Enterprise Accounting remains official, but Community Purchase has a technical dependency on `account`. Operational go-live must precede financial migration.

## Decision

Enterprise Accounting remains authoritative for all financial records before cutover. The Community `account` dependency may be installed technically, but LHI accounting operations, menus, jobs, endpoints and posting paths remain disabled through a server-enforced, fail-closed `lhi_accounting_enabled` feature flag. Activation requires formal migration approval.

## Consequences

The bridge initially exchanges only approved references/status with reconciliation. Install or upgrade cannot activate Accounting. Finance, Audit, Security and executive stakeholders must approve mappings, rehearsals, rollback and reconciliations before production activation.

