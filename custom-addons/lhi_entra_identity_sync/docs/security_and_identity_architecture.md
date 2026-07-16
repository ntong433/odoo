# Security and identity architecture

```text
Microsoft Entra ID
  ├─ authenticates the person
  ├─ supplies immutable object ID and profile
  ├─ supplies manager and organizational attributes
  └─ supplies membership in explicitly mapped functional groups
                │
                ▼
lhi_microsoft_graph_core
  ├─ protected client-secret app token cache
  ├─ retry / Retry-After / exponential backoff
  ├─ pagination bounds
  └─ redacted request diagnostics
                │
                ▼
lhi_entra_identity_sync
  ├─ dry-run and conflict plan
  ├─ protected administrator filter
  ├─ existing-group mapping only
  ├─ existing SoD rule evaluation
  ├─ transactional per-user apply
  └─ before/after snapshot and rollback
                │
                ▼
Existing LHI authorization
  ├─ res.groups XML IDs unchanged
  ├─ ACLs and record rules unchanged
  ├─ project assignments unchanged
  ├─ department/office rules enforced by Odoo
  └─ submitted approval approvers remain snapshotted
```

Entra is not consulted on ordinary Odoo requests. Authentication uses the
tenant-scoped OAuth provider. Background synchronization uses cached application
tokens and scheduled or queued reconciliation. If Graph is unavailable, the run
fails without removing local roles; existing authenticated sessions and last
successfully synchronized authorization state remain local. Protected maintenance
administrators retain the controlled local recovery path.

`checkMemberGroups` is called only with configured mapping object IDs, in chunks of
20. The operation is transitive, so approved nested group membership is recognized
without importing or treating every tenant group as an Odoo authorization object.
