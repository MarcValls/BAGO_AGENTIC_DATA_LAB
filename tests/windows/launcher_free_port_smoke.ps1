param([Parameter(Mandatory = $true)][string]$EvidencePath)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$launcher = Join-Path $repo 'scripts/run-local-ui.ps1'
$startedAt = [DateTime]::UtcNow
$global:BagoSmokeLauncherProcess = $null
$global:BagoSmokeBrowserSuppressed = $false
$global:BagoSmokeInjectFrontend = $null
$global:BagoSmokeInjectBackend = $null
$global:BagoSmokeFailReceiptMove = $false
$global:BagoSmokeNpmEntered = $false
$ownedListener = $null
$result = [ordered]@{ status = 'FAIL'; identity = @{}; checks = @{}; error = $null; error_stack = $null; cleanup_errors = @(); limits = @('Hosted Windows runner only.', 'Browser opening is suppressed for the initial launch. Optional focus result is recorded separately in browser-window.json.', 'No external provider inference is claimed.') }

if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This smoke test only runs on a GitHub-hosted ephemeral runner.'
}
if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -ne 0) {
    $result.error = 'Port 8080 was not free; refusing to start or stop any process.'
    $result.identity = @{ github_sha = $env:GITHUB_SHA; pull_request_head = $env:BAGO_SMOKE_PR_HEAD }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    throw $result.error
}

function Read-Host { param([Parameter(Position=0)][string]$Prompt) return '' }
function npm {
    $global:BagoSmokeNpmEntered = $true
    $command = Get-Command npm.cmd -CommandType Application -ErrorAction Stop | Select-Object -First 1
    & $command.Source @args
    if ($LASTEXITCODE -eq 0 -and $global:BagoSmokeInjectFrontend) {
        $marker = [IO.File]::Open($global:BagoSmokeInjectFrontend, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $marker.Dispose()
    }
}
function Move-Item {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$LiteralPath, [Parameter(Mandatory=$true)][string]$Destination, [switch]$Force)
    if ($global:BagoSmokeFailReceiptMove) { throw 'synthetic receipt publication failure' }
    Microsoft.PowerShell.Management\Move-Item @PSBoundParameters
}
function Start-Process {
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
    if ($global:BagoSmokeInjectBackend) {
        $marker = [IO.File]::Open($global:BagoSmokeInjectBackend, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $marker.Dispose()
    }
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
    $frontendMarker = Join-Path (Join-Path $repo 'frontend/src') ('bago-build-race-' + [guid]::NewGuid().ToString('N') + '.ts')
    try {
        $global:BagoSmokeInjectFrontend = $frontendMarker
        $failed = $null
        $failureRecord = $null
        try { & $launcher } catch { $failureRecord = $_; $failed = $_.Exception.Message }
        $result.checks.frontend_probe_error = $failed
        $result.checks.frontend_probe_error_id = if ($failureRecord) { $failureRecord.FullyQualifiedErrorId } else { $null }
        $result.checks.frontend_probe_stack = if ($failureRecord) { $failureRecord.ScriptStackTrace } else { $null }
        $result.checks.frontend_probe_npm_entered = $global:BagoSmokeNpmEntered
        $result.checks.frontend_probe_marker_created = Test-Path -LiteralPath $frontendMarker
        $result.checks.frontend_probe_server_launched = [bool]$global:BagoSmokeLauncherProcess
        $result.checks.frontend_probe_listener_count = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count
        if (-not $failed -or $failed -notmatch 'fuentes frontend cambiaron durante el build' -or $global:BagoSmokeLauncherProcess -or
            $result.checks.frontend_probe_listener_count -ne 0) { throw 'Frontend mutation did not block startup safely; see frontend_probe_error.' }
        $result.checks.frontend_change_during_build_blocks_start = $true
    } finally {
        $global:BagoSmokeInjectFrontend = $null
        [IO.File]::Delete($frontendMarker)
    }
    $backendMarker = Join-Path (Join-Path $repo 'src') ('bago-start-race-' + [guid]::NewGuid().ToString('N') + '.py')
    try {
        $global:BagoSmokeInjectBackend = $backendMarker
        $failed = $null
        try { & $launcher } catch { $failed = $_.Exception.Message }
        if (-not $failed -or $failed -notmatch 'started listener failed identity or asset checks') { throw 'Backend mutation did not block startup.' }
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -eq 0) { break }
            Start-Sleep -Milliseconds 250
        }
        if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Failed backend fixture was not stopped.' }
        $result.checks.backend_change_during_start_blocks_and_stops_fixture = $true
    } finally {
        $global:BagoSmokeInjectBackend = $null
        [IO.File]::Delete($backendMarker)
    }
    try {
        $global:BagoSmokeFailReceiptMove = $true
        $failed = $null
        try { & $launcher } catch { $failed = $_.Exception.Message }
        if (-not $failed -or $failed -notmatch 'No se pudo guardar el recibo.*limpieza del proceso iniciado: True') { throw 'Receipt publication failure was not handled.' }
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -eq 0) { break }
            Start-Sleep -Milliseconds 250
        }
        if (@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Receipt failure left a listener running.' }
        $result.checks.receipt_write_failure_stops_owned_fixture = $true
    } finally { $global:BagoSmokeFailReceiptMove = $false }
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
    $result.checks.free_before = $true
    $result.checks.launcher_started = $true
    $result.checks.one_loopback_listener = $true
    $result.checks.health = $true
    $result.checks.postflight_reuse_same_pid = $true
    $result.checks.listener_pid = $ownerId
    $result.checks.browser_launch_suppressed = $global:BagoSmokeBrowserSuppressed
    foreach ($case in @(@{ kind='backend'; dir='src'; ext='.py' }, @{ kind='frontend'; dir='frontend/src'; ext='.ts' }, @{ kind='dist'; dir='frontend/dist'; ext='.txt' })) {
        $marker = Join-Path (Join-Path $repo $case.dir) ('bago-smoke-' + [guid]::NewGuid().ToString('N') + $case.ext)
        $stream = [IO.File]::Open($marker, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Dispose()
        try {
            $changedOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
            $changedCode = $LASTEXITCODE
            $changed = ($changedOutput | Out-String | ConvertFrom-Json)
            if ($changedCode -ne 2 -or $changed.State -ne 'CONFLICT' -or [int]$changed.Pid -ne $ownerId) { throw "Changed $($case.kind) did not block reuse." }
            $result.checks["changed_$($case.kind)_blocks_reuse"] = $true
        } finally { [IO.File]::Delete($marker) }
    }
    $restoredOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
    $restored = ($restoredOutput | Out-String | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0 -or $restored.State -ne 'REUSE' -or [int]$restored.Pid -ne $ownerId) { throw 'Reuse of the same listener was not restored after fixture changes.' }
    $result.checks.fingerprints_restore_reuse = $true
    $stateDir = Join-Path $env:LOCALAPPDATA 'BAGO\AgentChat\instances'
    $matches = @(Get-ChildItem -LiteralPath $stateDir -File -Filter '*.json' | Where-Object {
        try { $item = Get-Content -Raw -LiteralPath $_.FullName | ConvertFrom-Json; [int]$item.listener_pid -eq $ownerId -and $item.repo_root -eq $repo } catch { $false }
    })
    if ($matches.Count -ne 1) { throw 'Cannot identify the exact fixture instance receipt.' }
    $receiptPath = $matches[0].FullName
    $receiptBytes = [IO.File]::ReadAllBytes($receiptPath)
    $backupPath = "$receiptPath.$([guid]::NewGuid().ToString('N')).fixture-backup"
    try {
        [IO.File]::Move($receiptPath, $backupPath)
        $missingOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
        $missingCode = $LASTEXITCODE
        $missing = ($missingOutput | Out-String | ConvertFrom-Json)
        if ($missingCode -ne 2 -or $missing.State -ne 'CONFLICT' -or [int]$missing.Pid -ne $ownerId) { throw 'Missing receipt did not block reuse of the same listener.' }
        [IO.File]::Move($backupPath, $receiptPath)
        [IO.File]::WriteAllText($receiptPath, '{invalid json')
        $corruptOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
        $corruptCode = $LASTEXITCODE
        $corrupt = ($corruptOutput | Out-String | ConvertFrom-Json)
        if ($corruptCode -ne 2 -or $corrupt.State -ne 'CONFLICT' -or [int]$corrupt.Pid -ne $ownerId) { throw 'Corrupt receipt did not block reuse of the same listener.' }
        $result.checks.missing_and_corrupt_receipts_block_reuse = $true
    } finally {
        if (Test-Path -LiteralPath $backupPath -PathType Leaf) { [IO.File]::Move($backupPath, $receiptPath) }
        else { [IO.File]::WriteAllBytes($receiptPath, $receiptBytes) }
    }
    $receiptRestoredOutput = & pwsh -NoProfile -NonInteractive -File $launcher -PreflightOnly
    $receiptRestored = ($receiptRestoredOutput | Out-String | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0 -or $receiptRestored.State -ne 'REUSE' -or [int]$receiptRestored.Pid -ne $ownerId) { throw 'Reuse of the same listener was not restored after receipt fixture.' }
    $result.checks.receipt_restored_reuse = $true
    & (Join-Path $PSScriptRoot 'browser_window_smoke.ps1') -EvidencePath (Join-Path (Split-Path $EvidencePath) 'browser-window.json') -ExpectedServerPid $ownerId
    $result.status = 'PASS'
} catch {
    $result.error = $_.Exception.Message
    $result.error_stack = $_.ScriptStackTrace
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
        $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    }
}
if ($result.status -ne 'PASS') { throw "Launcher smoke failed: $($result.error)" }
