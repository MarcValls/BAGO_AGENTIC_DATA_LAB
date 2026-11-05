param([Parameter(Mandatory = $true)][string]$EvidencePath)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$launcher = Join-Path $repo 'scripts/run-local-ui.ps1'
$startedAt = [DateTime]::UtcNow
$global:BagoSmokeLauncherProcess = $null
$global:BagoSmokeBrowserSuppressed = $false
$ownedListener = $null
$result = [ordered]@{ status = 'FAIL'; identity = @{}; checks = @{}; error = $null; cleanup_errors = @(); limits = @('Hosted Windows runner only.', 'Browser opening and focus are suppressed and NOT_RUN.', 'No external provider inference is claimed.') }

if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This smoke test only runs on a GitHub-hosted ephemeral runner.'
}
if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -ne 0) {
    $result.error = 'Port 8080 was not free; refusing to start or stop any process.'
    $result.identity = @{ github_sha = $env:GITHUB_SHA; pull_request_head = $env:BAGO_SMOKE_PR_HEAD }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    throw $result.error
}

function global:Read-Host { param([Parameter(Position=0)][string]$Prompt) return '' }
function global:Start-Process {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true, Position=0)][string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [System.Diagnostics.ProcessWindowStyle]$WindowStyle,
        [string]$RedirectStandardOutput,
        [string]$RedirectStandardError,
        [switch]$PassThru
    )
    if ($FilePath -eq 'http://127.0.0.1:8080') {
        $global:BagoSmokeBrowserSuppressed = $true
        return
    }
    if ($FilePath -notmatch '(?i)(?:^|[\\/])python(?:w)?(?:\d+(?:\.\d+)*)?\.exe$' -or
        ($ArgumentList -join ' ') -ne '-m src.api.server' -or -not $PassThru) {
        throw 'Unexpected process launch blocked by smoke harness.'
    }
    $global:BagoSmokeLauncherProcess = Microsoft.PowerShell.Management\Start-Process @PSBoundParameters
    return $global:BagoSmokeLauncherProcess
}

try {
    $checkout = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $checkout -notmatch '^[0-9a-f]{40}$' -or $checkout -ne $env:GITHUB_SHA) { throw 'Checkout identity does not match GITHUB_SHA.' }
    $result.identity = @{
        checkout = $checkout
        github_sha = $env:GITHUB_SHA
        pull_request_head = $env:BAGO_SMOKE_PR_HEAD
        launcher_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $launcher).Hash.ToLowerInvariant()
        smoke_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()
    }
    & $launcher
    $listeners = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -ne 1 -or $listeners[0].LocalAddress -ne '127.0.0.1') { throw 'Expected exactly one loopback listener.' }
    $ownerId = [int]$listeners[0].OwningProcess
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId"
    $process = Get-Process -Id $ownerId
    if (-not $global:BagoSmokeLauncherProcess -or $process.StartTime.ToUniversalTime() -lt $startedAt -or
        $owner.CommandLine -notmatch '(?i)\s-m\s+src\.api\.server(?:\s|$)' -or
        ($ownerId -ne $global:BagoSmokeLauncherProcess.Id -and [int]$owner.ParentProcessId -ne $global:BagoSmokeLauncherProcess.Id)) {
        throw 'Listener is not the process started by this smoke test.'
    }
    $ownedListener = [pscustomobject]@{ Id = $ownerId; StartTime = $process.StartTime; ParentId = [int]$owner.ParentProcessId; CommandLine = [string]$owner.CommandLine }
    $health = Invoke-RestMethod 'http://127.0.0.1:8080/api/health' -TimeoutSec 5
    if ($health.status -ne 'ok') { throw 'Health endpoint failed.' }
    $probeOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
    if ($LASTEXITCODE -ne 0) { throw 'Second preflight failed.' }
    $probe = ($probeOutput | Out-String | ConvertFrom-Json)
    if ($probe.State -ne 'REUSE' -or [int]$probe.Pid -ne $ownerId) { throw 'Second preflight did not reuse the started listener.' }
    $result.checks = @{ free_before = $true; launcher_started = $true; one_loopback_listener = $true; health = $true; postflight_reuse_same_pid = $true; listener_pid = $ownerId; browser_launch_suppressed = $global:BagoSmokeBrowserSuppressed }
    $result.status = 'PASS'
} catch {
    $result.error = $_.Exception.Message
} finally {
    $cleanupOk = $true
    try {
    # If the launcher failed after starting Python but before returning, recover
    # only a listener whose process identity and parent match this exact launch.
    if (-not $ownedListener -and $global:BagoSmokeLauncherProcess) {
        try {
        $remaining = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
        if ($remaining.Count -eq 1 -and $remaining[0].LocalAddress -eq '127.0.0.1') {
            $remainingId = [int]$remaining[0].OwningProcess
            $remainingInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$remainingId" -ErrorAction SilentlyContinue
            $remainingProcess = Get-Process -Id $remainingId -ErrorAction SilentlyContinue
            if ($remainingInfo -and $remainingProcess -and $remainingProcess.StartTime.ToUniversalTime() -ge $startedAt -and
                $remainingInfo.CommandLine -match '(?i)\s-m\s+src\.api\.server(?:\s|$)' -and
                ($remainingId -eq $global:BagoSmokeLauncherProcess.Id -or [int]$remainingInfo.ParentProcessId -eq $global:BagoSmokeLauncherProcess.Id)) {
                $ownedListener = [pscustomobject]@{ Id = $remainingId; StartTime = $remainingProcess.StartTime; ParentId = [int]$remainingInfo.ParentProcessId; CommandLine = [string]$remainingInfo.CommandLine }
            }
        }
        } catch { $cleanupOk = $false; $result.cleanup_errors += $_.Exception.Message }
    }
    if ($ownedListener) {
        try {
        $current = Get-Process -Id $ownedListener.Id -ErrorAction SilentlyContinue
        $info = Get-CimInstance Win32_Process -Filter "ProcessId=$($ownedListener.Id)" -ErrorAction SilentlyContinue
        if ($current -and $info -and $current.StartTime -eq $ownedListener.StartTime -and $info.CommandLine -eq $ownedListener.CommandLine) {
            Stop-Process -Id $ownedListener.Id -Force -ErrorAction Stop
        } elseif ($current) { $cleanupOk = $false }
        } catch { $cleanupOk = $false; $result.cleanup_errors += $_.Exception.Message }
    }
    if ($global:BagoSmokeLauncherProcess) {
        try {
        $parent = Get-Process -Id $global:BagoSmokeLauncherProcess.Id -ErrorAction SilentlyContinue
        if ($parent -and $parent.StartTime -eq $global:BagoSmokeLauncherProcess.StartTime) {
            Stop-Process -Id $parent.Id -Force -ErrorAction Stop
        } elseif ($parent) { $cleanupOk = $false }
        } catch { $cleanupOk = $false; $result.cleanup_errors += $_.Exception.Message }
    }
    Start-Sleep -Milliseconds 500
    if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -ne 0) { $cleanupOk = $false }
    } catch {
        $cleanupOk = $false
        $result.cleanup_errors += $_.Exception.Message
    } finally {
        $result.checks.cleanup_verified = $cleanupOk
        if (-not $cleanupOk) { $result.status = 'FAIL'; if (-not $result.error) { $result.error = 'Cleanup could not be verified.' } }
        try {
            $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
        } finally {
            Remove-Item Function:\global:Start-Process -ErrorAction SilentlyContinue
            Remove-Item Function:\global:Read-Host -ErrorAction SilentlyContinue
        }
    }
}
if ($result.status -ne 'PASS') { throw "Launcher smoke failed: $($result.error)" }
