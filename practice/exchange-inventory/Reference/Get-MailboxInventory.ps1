#requires -Version 7.0
[CmdletBinding(DefaultParameterSetName = 'Fixture')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Fixture')]
    [string] $InputCsv,
    [Parameter(Mandatory, ParameterSetName = 'Live')]
    [switch] $Live,
    [Parameter(Mandatory)]
    [string] $OutputCsv
)

$ErrorActionPreference = 'Stop'
$target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputCsv)
if ([IO.File]::Exists($target)) { throw "Choose a new output path. A file already exists at $target." }

$types = 'UserMailbox', 'SharedMailbox'
if ($PSCmdlet.ParameterSetName -eq 'Live') {
    if (-not $Live) { throw 'Use -Live to explicitly request a connected session.' }
    $mailboxes = @(Get-EXOMailbox -RecipientTypeDetails $types -ResultSize Unlimited -ErrorAction Stop)
} else {
    if (-not (Test-Path -LiteralPath $InputCsv -PathType Leaf)) { throw "Input file missing: $InputCsv" }
    $header = Get-Content -LiteralPath $InputCsv -TotalCount 1
    # Parse the header with the CSV parser so both quoted and unquoted names work.
    $headerProbe = @(($header, 'x,x,x') | ConvertFrom-Csv)
    $fields = @('DisplayName', 'PrimarySmtpAddress', 'RecipientTypeDetails')
    if (-not $header -or -not $headerProbe -or @($fields | Where-Object { $_ -notin $headerProbe[0].PSObject.Properties.Name }).Count) {
        throw 'Expected CSV columns DisplayName, PrimarySmtpAddress and RecipientTypeDetails.'
    }
    $mailboxes = @(Import-Csv -LiteralPath $InputCsv -Encoding utf8)
}
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$rows = @(foreach ($mailbox in $mailboxes) {
    if ($mailbox.RecipientTypeDetails -notin $types) { continue }
    $address = ([string]$mailbox.PrimarySmtpAddress).Trim()
    if (-not $address) { throw 'An included mailbox has no primary address.' }
    if (-not $seen.Add($address)) { throw "Duplicate primary address: $address" }
    [pscustomobject][ordered]@{
        DisplayName          = [string]$mailbox.DisplayName
        PrimarySmtpAddress   = $address
        RecipientTypeDetails = [string]$mailbox.RecipientTypeDetails
    }
})

$dir = [IO.Path]::GetDirectoryName($target)
$temp = Join-Path $dir ([IO.Path]::GetRandomFileName())
try {
    if ($rows.Count) {
        $rows | Sort-Object PrimarySmtpAddress | Export-Csv -LiteralPath $temp -NoTypeInformation -Encoding utf8NoBOM
    } else {
        '"DisplayName","PrimarySmtpAddress","RecipientTypeDetails"' | Set-Content -LiteralPath $temp -Encoding utf8NoBOM
    }
    [IO.File]::Move($temp, $target)
} finally {
    if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
}
