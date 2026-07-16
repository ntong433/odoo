[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$TenantAdminUrl,

    [Parameter(Mandatory = $true)]
    [string]$SiteUrl,

    [Parameter(Mandatory = $true)]
    [string]$SiteOwner,

    [string]$SiteTitle = "LHI ERP",

    [string]$ProjectCode,

    [string]$ConfigurationPath = "$PSScriptRoot/sharepoint_structure.json"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Module -ListAvailable -Name PnP.PowerShell)) {
    throw "PnP.PowerShell is required. Install it in an approved administrator workstation."
}

$configuration = Get-Content -Raw -Path $ConfigurationPath | ConvertFrom-Json

Connect-PnPOnline -Url $TenantAdminUrl -Interactive
$site = Get-PnPTenantSite -Identity $SiteUrl -ErrorAction SilentlyContinue
if (-not $site) {
    if ($PSCmdlet.ShouldProcess($SiteUrl, "Create the LHI ERP SharePoint site")) {
        New-PnPTenantSite `
            -Title $SiteTitle `
            -Url $SiteUrl `
            -Owner $SiteOwner `
            -Template "STS#3" `
            -TimeZone 25 `
            -RemoveDeletedSite
    }
}

Connect-PnPOnline -Url $SiteUrl -Interactive

$documentClassChoices = [string[]]$configuration.documentClasses
$retentionChoices = [string[]]$configuration.retentionCategories

foreach ($column in $configuration.siteColumns) {
    $existingField = Get-PnPField -Identity $column.internalName -ErrorAction SilentlyContinue
    if ($existingField) {
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($column.displayName, "Create SharePoint site column")) {
        continue
    }
    switch ($column.type) {
        "Choice" {
            $choices = if ($column.internalName -eq "LhiDocumentClass") {
                $documentClassChoices
            } else {
                $retentionChoices
            }
            Add-PnPField `
                -DisplayName $column.displayName `
                -InternalName $column.internalName `
                -Type Choice `
                -Choices $choices `
                -Group "LHI ERP" `
                -Required:$column.required
        }
        "Integer" {
            Add-PnPField `
                -DisplayName $column.displayName `
                -InternalName $column.internalName `
                -Type Integer `
                -Group "LHI ERP" `
                -Required:$column.required
        }
        default {
            Add-PnPField `
                -DisplayName $column.displayName `
                -InternalName $column.internalName `
                -Type Text `
                -Group "LHI ERP" `
                -Required:$column.required
        }
    }
}

$contentType = Get-PnPContentType -Identity "LHI Business Document" -ErrorAction SilentlyContinue
if (-not $contentType -and $PSCmdlet.ShouldProcess("LHI Business Document", "Create content type")) {
    Add-PnPContentType `
        -Name "LHI Business Document" `
        -Description "LHI ERP-managed business document metadata." `
        -Group "LHI ERP" `
        -ParentContentType "Document"
    $contentType = Get-PnPContentType -Identity "LHI Business Document"
}

if ($contentType) {
    foreach ($column in $configuration.siteColumns) {
        $linked = Get-PnPProperty -ClientObject $contentType -Property FieldLinks |
            Where-Object { $_.Name -eq $column.internalName }
        if (-not $linked -and $PSCmdlet.ShouldProcess(
            "$($column.internalName) -> LHI Business Document",
            "Link field to content type"
        )) {
            Add-PnPFieldToContentType `
                -Field $column.internalName `
                -ContentType $contentType.Name
        }
    }
}

foreach ($libraryName in $configuration.libraries) {
    $library = Get-PnPList -Identity $libraryName -ErrorAction SilentlyContinue
    if (-not $library -and $PSCmdlet.ShouldProcess($libraryName, "Create document library")) {
        New-PnPList `
            -Title $libraryName `
            -Template DocumentLibrary `
            -OnQuickLaunch
        $library = Get-PnPList -Identity $libraryName
    }
    if (-not $library) {
        continue
    }
    if ($PSCmdlet.ShouldProcess($libraryName, "Enable versioning and content types")) {
        Set-PnPList `
            -Identity $libraryName `
            -EnableVersioning $true `
            -EnableMinorVersions $false `
            -MajorVersions 100 `
            -EnableContentTypes $true
        if ($contentType) {
            Add-PnPContentTypeToList `
                -List $libraryName `
                -ContentType $contentType.Name `
                -DefaultContentType
        }
    }
}

$web = Get-PnPWeb -Includes Id,Url,Title,ServerRelativeUrl
$documentLibrary = Get-PnPList -Identity $configuration.libraries[0] -Includes Id,RootFolder
$webRelativeUrl = $web.ServerRelativeUrl.TrimEnd("/")
$libraryRelativeUrl = $documentLibrary.RootFolder.ServerRelativeUrl
if ($webRelativeUrl -and $libraryRelativeUrl.StartsWith($webRelativeUrl)) {
    $libraryRelativeUrl = $libraryRelativeUrl.Substring($webRelativeUrl.Length)
}
$libraryRelativeUrl = $libraryRelativeUrl.TrimStart("/")
$erpRoot = "$libraryRelativeUrl/$($configuration.rootFolder)"

if ($PSCmdlet.ShouldProcess($erpRoot, "Create the ERP document root")) {
    Resolve-PnPFolder -SiteRelativePath $erpRoot | Out-Null
    foreach ($folder in $configuration.rootFolders) {
        Resolve-PnPFolder -SiteRelativePath "$erpRoot/$folder" | Out-Null
    }
}

if ($ProjectCode) {
    if ($ProjectCode -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$") {
        throw "ProjectCode contains unsupported SharePoint path characters."
    }
    $projectRoot = "$erpRoot/Projects/$ProjectCode"
    if ($PSCmdlet.ShouldProcess($projectRoot, "Create project workspace template")) {
        Resolve-PnPFolder -SiteRelativePath $projectRoot | Out-Null
        foreach ($folder in $configuration.projectFolders) {
            Resolve-PnPFolder -SiteRelativePath "$projectRoot/$folder" | Out-Null
        }
    }
}

$lists = foreach ($libraryName in $configuration.libraries) {
    $library = Get-PnPList -Identity $libraryName -Includes Id,RootFolder
    [pscustomobject]@{
        Name = $libraryName
        ListId = $library.Id
        ServerRelativeUrl = $library.RootFolder.ServerRelativeUrl
    }
}

[pscustomobject]@{
    SiteTitle = $web.Title
    SiteUrl = $web.Url
    SharePointWebId = $web.Id
    ErpRoot = $erpRoot
    Libraries = $lists
    RetentionNote = "Map approved Microsoft Purview retention labels after Records Management approval."
} | ConvertTo-Json -Depth 5
