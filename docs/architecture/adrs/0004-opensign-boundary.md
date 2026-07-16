# ADR-0004: OpenSign Signature Boundary

- Status: Proposed
- Date: 2026-07-15

## Context

Odoo owns business workflows while LHI OpenSign performs configured final signatures. The current prototype callback lacks adequate authenticity and replay controls.

## Decision

Odoo owns signature intent, eligibility and the business-record link. OpenSign owns the ceremony, signer evidence, signed artifact and certificate. Integration uses dedicated service authentication, signed and idempotent events, authenticated artifact retrieval, correlation IDs and document hashes.

## Consequences

Callbacks cannot choose arbitrary Odoo models/records or download hosts. Completion is accepted only after server validation. Retries and duplicates are safe, failures are queued, and signed evidence has explicit retention and restricted access.

