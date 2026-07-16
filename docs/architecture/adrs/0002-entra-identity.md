# ADR-0002: Entra Identity and Odoo Authorization

- Status: Proposed
- Date: 2026-07-15

## Context

LHI needs one organizational identity across Odoo, Leave and OpenSign while Odoo still requires application-specific authorization.

## Decision

Microsoft Entra ID owns authentication identity and account lifecycle. Odoo uses tenant-restricted OIDC/OAuth and stores the immutable Entra object ID as the unique join key. Odoo owns fine-grained ERP groups, ACLs, record rules and business authorization, optionally assigned from approved Entra group mappings.

## Consequences

Email is not an identity key. Provisioning, group removal, account disablement and break-glass access need tests and audit. Graph scopes remain least-privilege. Hiding UI elements never substitutes for server authorization.

