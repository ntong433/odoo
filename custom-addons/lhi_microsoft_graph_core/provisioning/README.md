# SharePoint provisioning assets

- `sharepoint_structure.json` defines the `Documents` library, the `ERP` root,
  governed category folders, columns, document classes, retention categories,
  and the project folder template.
- `Provision-LhiSharePoint.ps1` idempotently creates or validates the site
  structure with PnP.PowerShell and supports `-WhatIf`.
- `Grant-LhiSitesSelected.ps1` assigns the approved application to one site and
  supports `-WhatIf`.

Run these scripts only from an approved administrator workstation. Review all
identifiers before removing `-WhatIf`. The scripts do not contain tenant IDs,
site IDs, application IDs, credentials, or passwords.

The SharePoint script does not publish Purview retention labels. Retention
configuration requires records-management and legal approval.
