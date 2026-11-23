#requires -Version 7.0
[CmdletBinding()]
param([string] $Script = (Join-Path $PSScriptRoot 'Get-MailboxInventory.ps1'))
$ErrorActionPreference = 'Stop'
$Script = (Resolve-Path -LiteralPath $Script).Path
$fixture = Join-Path $PSScriptRoot 'mailboxes.csv'
$temp = [IO.Directory]::CreateDirectory((Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString()))).FullName
function Confirm([bool] $pass, [string] $details) { if (-not $pass) { throw $details } }
function Confirm-Failure([scriptblock] $action, [string] $details) {
    $failed = $false
    try { & $action } catch { $failed = $true }
    Confirm $failed $details
}
# The only live reader permitted by the brief is replaced here by a local test double.
function Get-EXOMailbox {
    [CmdletBinding()]
    param([string[]] $RecipientTypeDetails, [string] $ResultSize)
    Confirm (($RecipientTypeDetails | Sort-Object) -join ',' -eq 'SharedMailbox,UserMailbox') 'Unexpected recipient types.'
    Confirm ($ResultSize -eq 'Unlimited') 'The reader needs all pages of mailbox results.'
    $inventoryTestState.ReadCalls++
    if ($inventoryTestState.Interrupt) {
        (Import-Csv -LiteralPath $fixture)[0]
        throw 'Simulated interruption during collection.'
    }
    Import-Csv -LiteralPath $fixture | Where-Object RecipientTypeDetails -In $RecipientTypeDetails
}
$inventoryTestState = [pscustomobject]@{ ReadCalls = 0; Interrupt = $false }
try {
    $out = Join-Path $temp 'report.csv'
    & $Script -InputCsv $fixture -OutputCsv $out
    Confirm ($inventoryTestState.ReadCalls -eq 0) 'Fixture mode tried the Exchange reader.'
    $rows = @(Import-Csv -LiteralPath $out)
    Confirm ($rows.Count -eq 4) 'Expected exactly four rows.'
    Confirm (($rows[0].PSObject.Properties.Name -join ',') -ceq 'DisplayName,PrimarySmtpAddress,RecipientTypeDetails') 'Unexpected columns.'
    Confirm (($rows.PrimarySmtpAddress -join ',') -ceq 'accounts@example.test,box-a@example.test,box-b@example.test,box-c@example.test') 'Filter or sort mismatch.'
    Confirm (($rows.RecipientTypeDetails -join ',') -ceq 'SharedMailbox,UserMailbox,SharedMailbox,UserMailbox') 'Mailbox type mismatch.'
    Confirm ($rows[1].DisplayName -ceq 'Team, Blue' -and $rows[3].DisplayName -ceq 'Café Desk') 'CSV quoting or Unicode mismatch.'
    'PASS 1 - fixture rows, types, sort, columns and names'

    $header = Get-Content -LiteralPath $fixture -TotalCount 1
    $empty = Join-Path $temp 'empty.csv'
    $header | Set-Content -LiteralPath $empty
    $zero = Join-Path $temp 'zero.csv'
    & $Script -InputCsv $empty -OutputCsv $zero
    $lines = @(Get-Content -LiteralPath $zero)
    Confirm ($lines.Count -eq 1 -and $lines[0].Replace('"','') -ceq $header) 'Empty report must contain only the correct header.'
    'PASS 2 - empty input retains its header'

    $bad = Join-Path $temp 'invalid.csv'
    $badOut = Join-Path $temp 'invalid-output.csv'
    foreach ($invalid in @('Duplicate,BOX-A@example.test,UserMailbox','Missing,,SharedMailbox')) {
        $source = @(Get-Content -LiteralPath $fixture) + $invalid
        $source | Set-Content -LiteralPath $bad
        Confirm-Failure { & $Script -InputCsv $bad -OutputCsv $badOut } 'Expected invalid input to stop the report.'
        Confirm (-not (Test-Path -LiteralPath $badOut)) 'A failed run published an output file.'
    }
    'PASS 3 - duplicate and missing addresses fail cleanly'

    $originalHash = (Get-FileHash -LiteralPath $out).Hash
    Confirm-Failure { & $Script -InputCsv $fixture -OutputCsv $out } 'Existing output should cause a failure.'
    Confirm ((Get-FileHash -LiteralPath $out).Hash -eq $originalHash) 'Existing report changed.'
    'PASS 4 - existing output preserved'

    $fakeLive = Join-Path $temp 'mock-live.csv'
    & $Script -Live -OutputCsv $fakeLive
    Confirm ($inventoryTestState.ReadCalls -eq 1) 'Expected one simulated Get-EXOMailbox call.'
    Confirm ((Get-FileHash -LiteralPath $fakeLive).Hash -eq $originalHash) 'Fixture and simulated live reports differ.'
    $inventoryTestState.Interrupt = $true
    $interrupted = Join-Path $temp 'interrupted.csv'
    Confirm-Failure { & $Script -Live -OutputCsv $interrupted } 'Interrupted live reads should fail.'
    Confirm (-not (Test-Path -LiteralPath $interrupted)) 'An interrupted read left a partial report.'
    'PASS 5 - simulated Exchange reader and interrupted collection'
} finally {
    [IO.Directory]::Delete($temp, $true)
}
