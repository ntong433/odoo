# Asset Register User Guide

## Register an asset

Create the asset in Operations → Asset Register → All Assets. Complete its
category, configurable condition, legal owner, registration state, currency,
and the applicable acquisition, project, programme, donor, funding, office,
HUB, location, custody, value, warranty, and restriction details.

For a new asset, leave Asset Tag empty and select Confirm Registration. LHI ERP
allocates the configured tag atomically. If the asset already has a legacy
Asset Number, enter it exactly; confirmation preserves and classifies it.

## Move, assign, repair, lose, or dispose of an asset

Use a Transfer and Disposal record. Do not overwrite the current state,
location, HUB, custodian, legal owner, or status to hide a movement. Submit the
workflow, allow the configured approval route to finish, then complete it. The
origin state embedded in the asset tag never changes.

## Re-tag an asset

Create a Re-tag Request with a specific reason. A different Asset Manager must
approve it. LHI ERP allocates a new unique tag and permanently records the old
tag, reason, requester, approver, and timestamps.

## Import a legacy register

Upload CSV or XLSX without renaming existing columns. `Purchase Vaue`,
`cat_cal`, `Asset SN`, and `Asset Number` are explicitly supported. Preview,
correct, and validate every row. Errors are never silently skipped. An empty
Asset Number is generated only when required category/state/owner information
can be resolved.

## Documents and reports

Use SharePoint Documents on the asset for durable business files. Printable
actions provide the register, barcode/QR label, condition report, and
handover/transfer/disposal record.
