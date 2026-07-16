# Sprint 7 Delivery Summary: Existing Attachment Migration

## Objectives Met
Safely architected the `lhi_document_migration` module to extract historical attachments from the local Odoo database/filestore and push them into the secure, partitioned SharePoint storage tier without breaking any relational links, approvals, or audit histories.

## Deliverables

### 1. Classification & Duplicate Detection
- Built `lhi.document.migration.job` to inventory existing `ir.attachment` records.
- **Rules Engine**: Classifies files intelligently into Business Documents (to migrate), Technical/Web assets (to retain locally), Duplicates, and Missing/Corrupt instances.

### 2. Destination Mapping & Checksum Verification
- Generates `lhi.document.migration.mapping` entries.
- Determines the exact logical SharePoint Partition (`lhi_sharepoint_sync`) based on the Odoo parent record (e.g., matching the attachment to its specific Project/Grant code).
- Calculates the local checksum and guarantees that upon successful migration, the returned SharePoint checksum matches perfectly before marking the migration state as `verified`.

### 3. Dry-Run & Batch Execution
- Includes a dedicated `Dry Run Mode`. This simulates the target partition logic and checksum computations without executing the heavy API upload phase. 
- Allows for chunking batches via the `batch_size` parameter. Supports idempotency—running the same batch twice evaluates the `verified` state, explicitly preventing duplicate file creation in SharePoint.

### 4. Controlled Local Purge
- By default, successfully migrated files are preserved locally until final administrator approval.
- An independent `action_local_purge` sweeps only files flagged as `verified`. As requested, this operation is strictly gated by the system environment variable (`DOCUMENT_LOCAL_PURGE_ENABLED`), throwing a `UserError` if attempted without explicit authorization.

### 5. Rollback Support
- Mappings can be undone (`action_rollback`), dropping the SharePoint link reference and reverting the status back to `draft` if a migration step requires recalculation.

## Security & Reliability
- No Odoo relationships, audit logs, or cryptographic signatures are destroyed.
- Python tests cover the prevention of accidental local purges and validate the dry-run capabilities. All test cases passed successfully in the sandbox environment.
