# Asset Register Administrator Guide

## Initial configuration

1. Assign users only the required operational role:
   Asset Officer, Asset Manager, or System Auditor.
2. For limited Asset Officers, set their permitted offices and projects on the
   Odoo user record. No employee record is required.
3. In Operations → Asset Register → Configuration, configure:
   asset categories and codes, conditions, physical locations, and one active
   default asset-tag rule per company.
4. On each applicable Nigerian state record, set the LHI Asset Tag Code
   (examples: `EBO`, `BAU`).
5. Configure approval matrices with document types Asset Transfer and Asset
   Disposal. Use specific users or the Asset Manager group and preserve
   segregation of duties.
6. Verify the existing Microsoft Graph connection and the SharePoint
   `operations` library. Import source files fail closed if SharePoint does not
   confirm storage.

## Tag strategies

- Global: one monotonically increasing organisation sequence.
- Owner: independent sequence per LHI/project owner segment.
- Prefix: independent sequence per owner/state/category prefix.

Changing the strategy affects only future allocations. Never delete tag
counters. Confirmed tags can change only through an approved Re-tag Request.

## Import administration

The source workbook is uploaded to SharePoint before preview. Correct preview
rows, validate, review every explicit error, then import valid rows. Use the
downloadable error report for corrections. A batch can be rolled back only by
an Asset Manager and only while its assets have no transfer, re-tag, disposal,
or other downstream lifecycle events.

## Approval configuration

Transfer/disposal submission fails if no active matching matrix exists. This is
intentional and fail-closed. A workflow cannot complete until its reusable
`lhi.approval.request` is fully approved. Requesters cannot approve their own
current stage.

## Operational checks

- Asset Register Overview opens without an employee record.
- A limited Asset Officer sees only company/office/project-permitted assets.
- A minimal internal user has no asset access.
- Generated tags and serial numbers cannot duplicate.
- Moving an asset between states does not change its origin-state tag.
- SharePoint documents show only after confirmed upload.
- Reports render barcodes and QR codes.
