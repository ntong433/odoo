# LHI Entra Identity Sync

`lhi_entra_identity_sync` makes Microsoft Entra ID the organizational identity
source while preserving the existing LHI Odoo groups, ACLs, record rules,
project assignments, approval matrices, segregation-of-duties rules, and
administrator protections as the authorization engine.

The module provides:

- immutable Entra object-ID matching with controlled first-time UPN/email matching;
- paginated Graph user reconciliation and transitive membership checks limited to
  approved mapped Entra group IDs;
- dry-run, write, failure-retry, diagnostics, immutable snapshots, and drift-safe
  rollback;
- manager synchronization to the existing HR employee reporting line;
- explicit manager reassignment for already submitted approvals;
- protected technical and maintenance administrators;
- configurable disabled-account handling;
- tenant-scoped primary Entra login; and
- a source-network-restricted local maintenance login route.

The module does not create functional Odoo groups and does not implement a second
RBAC engine.

