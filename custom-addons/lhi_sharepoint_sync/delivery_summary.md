# Sprint 6 Delivery Summary: SharePoint Sync and Scale Protection

## Objectives Met
Successfully addressed the Microsoft SharePoint 5,000 list-view threshold constraints by introducing a robust logical partitioning and metadata-indexing engine natively within Odoo.

## Deliverables

### 1. Partitioning and Storage Safety (`lhi.sharepoint.partition`)
- **Logical Mapping**: Documents are no longer dumped into a single monolithic library. Partitions are divided by Domain, Year, and Project.
- **Capacity Monitoring**: Implemented safety thresholds. When a partition reaches 4,000 items, an alert is triggered. At 4,500 items, the partition automatically flips to Read-Only (`routing_threshold`), enforcing new uploads to route to a new partition.
- **Fail-Closed Strategy**: Documents never save to Odoo first; Odoo strictly stores the `drive_item_id` (Immutable ID) ensuring full byte-ownership by SharePoint.

### 2. Scoped and Indexed Metadata Queries (`lhi.document.metadata`)
- Created an Odoo-native index of key document attributes: `ProjectCode`, `AwardCode`, `DocumentCategory`, `ReportingYear`, etc.
- **Unbounded Query Prevention**: The method `get_scoped_documents()` enforces bounded searches with limit and offset (server-side pagination). It fundamentally prevents querying a whole library.

### 3. Graph Change Notifications (`graph_notifications.py`)
- Exposes `https://work.lhinigeria.org/lhi/graph/notifications` as the webhook listener.
- **Challenge Validation**: Handles initial Microsoft Graph subscription verification.
- **Asynchronous Processing**: Responds with `202 Accepted` immediately as per Microsoft SLA (< 3s), leaving actual payload extraction to the delta sync engine.

### 4. Delta Synchronization (`lhi.sharepoint.delta`)
- Manages Delta Link persistence per partition.
- Ensures moves, renames, and deletions in SharePoint natively reflect in Odoo's metadata without heavy full-library scans.

### 5. Reconciliation Jobs (`lhi.document.reconciliation`)
- Introduced the skeleton for periodic reconciliation comparing Odoo metadata against SharePoint DriveItems (e.g., identifying failed uploads, stale eTags, or orphaned files).

## Security & Reliability
- No unique item-level permissions are dynamically generated; security leverages inherited scopes per folder/site.
- Python tests cover partition routing and scoped queries, successfully passing in the containerized environment.
