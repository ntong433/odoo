[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$SiteId,

    [Parameter(Mandatory = $true)]
    [string]$ApplicationClientId,

    [string]$ApplicationDisplayName = "LHI ERP Microsoft Graph",

    [ValidateSet("read", "write")]
    [string]$Role = "write"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Authentication)) {
    throw "Microsoft.Graph.Authentication is required on the approved administrator workstation."
}

# The administrator session is used only to assign the selected resource.
# The runtime Odoo application retains Sites.Selected and cannot grant itself other sites.
Connect-MgGraph -Scopes "Sites.FullControl.All" -NoWelcome

$body = @{
    roles = @($Role)
    grantedToIdentities = @(
        @{
            application = @{
                id = $ApplicationClientId
                displayName = $ApplicationDisplayName
            }
        }
    )
} | ConvertTo-Json -Depth 5

$uri = "https://graph.microsoft.com/v1.0/sites/$SiteId/permissions"
if ($PSCmdlet.ShouldProcess($SiteId, "Grant $Role Sites.Selected access to $ApplicationClientId")) {
    Invoke-MgGraphRequest `
        -Method POST `
        -Uri $uri `
        -Body $body `
        -ContentType "application/json"
}

Invoke-MgGraphRequest -Method GET -Uri $uri |
    ConvertTo-Json -Depth 8

