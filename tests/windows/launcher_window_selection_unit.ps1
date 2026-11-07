$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot '../../scripts/run-local-ui.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $launcher), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Launcher parse failed.' }
$functionAst = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Resolve-BrowserWindowAction' }, $true)
if (-not $functionAst) { throw 'Missing browser window selector.' }
Invoke-Expression $functionAst.Extent.Text

function Get-VisibleBrowserWindows { return $script:windows }
function Read-Host { $script:prompts++; return $script:answer }
function Window([int]$id, [string]$state) {
    [pscustomobject]@{ ProcessId = $id; AddressState = $state; Title = "Window $id" }
}
function Check([bool]$condition, [string]$message) { if (-not $condition) { throw $message } }

$script:prompts = 0
$script:windows = @((Window 10 'MATCH'), (Window 20 'OTHER'))
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'focus' -and $result.Window.ProcessId -eq 10 -and $result.BagoRecognized -and $script:prompts -eq 0) 'Unique match must focus without asking.'

$script:windows = @((Window 10 'MATCH'), (Window 20 'UNKNOWN'))
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'focus' -and $result.Window.ProcessId -eq 10 -and $result.BagoRecognized -and $script:prompts -eq 0) 'Unique observable match with unknown window must focus without asking.'

$script:windows = @((Window 10 'MATCH'), (Window 20 'MATCH'))
$script:answer = '20'
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'focus' -and $result.Window.ProcessId -eq 20 -and $script:prompts -eq 1) 'Multiple matches must ask for PID.'

$script:answer = ''
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'skip' -and $script:prompts -eq 2) 'Cancelling an ambiguous selection must skip.'

foreach ($invalid in @('not-a-pid', '999')) {
    $script:answer = $invalid
    $rejected = $false
    try { $null = Resolve-BrowserWindowAction } catch { $rejected = $true }
    Check $rejected "Invalid PID '$invalid' must be rejected."
}
Check ($script:prompts -eq 4) 'Each invalid selection must prompt.'

$script:windows = @((Window 30 'UNKNOWN'))
$script:answer = ''
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'skip' -and $script:prompts -eq 5) 'Unknown window with blank answer must skip.'

$script:windows = @()
$result = Resolve-BrowserWindowAction
Check ($result.Action -eq 'launch' -and $script:prompts -eq 5) 'No windows must preserve launch behavior.'

Write-Output 'PASS: unique, ambiguous, unknown and absent browser window selection.'
