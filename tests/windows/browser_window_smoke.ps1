param([Parameter(Mandatory = $true)][string]$EvidencePath, [Parameter(Mandatory = $true)][int]$ExpectedServerPid)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This test is restricted to a GitHub-hosted runner.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$launcher = Join-Path $repo 'scripts/run-local-ui.ps1'
$result = [ordered]@{
    status = 'NOT_RUN'; reason = $null; checks = @{}; error = $null
    identity = @{}; cleanup_errors = @()
    limits = @('Hosted runner only.', 'PID response simulated.', 'Real launcher REUSE path is checked only when a window is available.', 'Foreground equality does not prove a transition from a different window.', 'Opening through the launcher, tab count and actual user input are NOT_RUN.', 'Cleanup covers only the directly launched browser PID; profile and child processes remain subject to VM disposal.')
}
$browser = $null
$browserStart = $null
try {
    $checkout = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $checkout -ne $env:GITHUB_SHA) { throw 'Checkout identity mismatch.' }
    $result.identity = @{ checkout = $checkout; pull_request_head = $env:BAGO_SMOKE_PR_HEAD; launcher_sha256 = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant(); test_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class BagoWindowSmokeApi {
    [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] public static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
'@
    $desktop = [BagoWindowSmokeApi]::OpenInputDesktop(0, $false, 1)
    if ($desktop -eq [IntPtr]::Zero) {
        $result.reason = 'No accessible input desktop.'
    } else {
        [BagoWindowSmokeApi]::CloseDesktop($desktop) | Out-Null
        $roots = @(${env:ProgramFiles}, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
        $browserPath = $null
        foreach ($base in $roots) {
            foreach ($relative in @('Google\Chrome\Application\chrome.exe', 'Microsoft\Edge\Application\msedge.exe')) {
                $candidate = Join-Path $base $relative
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $browserPath = $candidate; break }
            }
            if ($browserPath) { break }
        }
        if (-not $browserPath) {
            $result.reason = 'No supported browser installed in runner.'
        } else {
            $profile = Join-Path $env:RUNNER_TEMP ('bago-window-' + [guid]::NewGuid().ToString('N'))
            $arguments = @("--user-data-dir=$profile", '--no-first-run', '--no-default-browser-check', '--new-window', 'about:blank')
            $browser = Microsoft.PowerShell.Management\Start-Process -FilePath $browserPath -ArgumentList $arguments -PassThru
            $browserStart = $browser.StartTime
            $window = $null
            for ($attempt = 0; $attempt -lt 40; $attempt++) {
                Start-Sleep -Milliseconds 500
                $process = Get-Process -Id $browser.Id -ErrorAction SilentlyContinue
                if (-not $process) { throw 'Browser fixture exited before producing a window.' }
                if ($process.StartTime -ne $browserStart) { throw 'Browser fixture PID identity changed.' }
                if ($process.MainWindowHandle -ne [IntPtr]::Zero) { $window = $process.MainWindowHandle; break }
            }
            if (-not $window) {
                $result.reason = 'Browser fixture has no observable window in runner session.'
            } else {
                $errors = $null; $tokens = $null
                $ast = [System.Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
                if ($errors.Count) { throw 'Launcher parse failed.' }
                foreach ($name in @('Get-VisibleBrowserWindows', 'Test-LocalUiAddress', 'Get-VisibleBrowserAddressState', 'Resolve-BrowserWindowAction', 'Focus-BrowserWindow')) {
                    $node = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true)
                    if (-not $node) { throw "Missing launcher function: $name" }
                    . ([scriptblock]::Create($node.Extent.Text))
                }
                $browserFixturePid = $browser.Id
                function Read-Host { param([string]$Prompt) return "$browserFixturePid" }
                    $action = Resolve-BrowserWindowAction
                    if ($action.Action -ne 'focus' -or $action.Window.ProcessId -ne $browser.Id -or $action.Window.Handle -ne $window) { throw 'Fixture PID did not select its own browser window.' }
                    $result.checks.pid_selected = $true
                    $focused = Focus-BrowserWindow $action.Window
                    if (-not $focused) {
                        $current = Get-Process -Id $browser.Id -ErrorAction SilentlyContinue
                        if (-not $current -or $current.StartTime -ne $browserStart -or $current.MainWindowHandle -ne $window) { throw 'Fixture window disappeared or changed during focus.' }
                        $result.status = 'OS_DENIED'
                        $result.reason = 'Windows declined the foreground request.'
                    } else {
                        Start-Sleep -Milliseconds 300
                        if ([BagoWindowSmokeApi]::GetForegroundWindow() -ne $window) { throw 'Foreground HWND does not match fixture window.' }
                        $listeners = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
                        if ($listeners.Count -ne 1 -or [int]$listeners[0].OwningProcess -ne $ExpectedServerPid -or $listeners[0].LocalAddress -ne '127.0.0.1') { throw 'Fixture server identity changed before REUSE.' }
                        $launcherOutput = (& $launcher | Out-String)
                        if ($launcherOutput -notmatch "Ventana seleccionada enfocada \(PID $($browser.Id)\)" -or [BagoWindowSmokeApi]::GetForegroundWindow() -ne $window) { throw 'Real launcher did not focus the selected fixture window.' }
                        $listenersAfter = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
                        if ($listenersAfter.Count -ne 1 -or [int]$listenersAfter[0].OwningProcess -ne $ExpectedServerPid) { throw 'Fixture server changed during REUSE.' }
                        $result.checks.foreground_hwnd_matches = $true
                        $result.checks.real_launcher_reused_server_and_focused_selected_pid = $true
                        $result.status = 'PASS'
                    }
            }
        }
    }
} catch {
    $result.status = 'FAIL'; $result.error = $_.Exception.Message; $result.error_stack = $_.ScriptStackTrace
} finally {
    try {
        if ($browser) {
            $process = Get-Process -Id $browser.Id -ErrorAction SilentlyContinue
            if ($process -and $process.StartTime -eq $browserStart) { Stop-Process -Id $browser.Id -Force -ErrorAction Stop }
            elseif ($process) { throw 'Browser PID identity changed; no process stopped.' }
            $result.checks.direct_browser_pid_cleanup_attempted = $true
        }
    } catch { $result.status = 'FAIL'; $result.cleanup_errors += $_.Exception.Message }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
    if ($env:GITHUB_STEP_SUMMARY) {
        @("### Browser window selection: $($result.status)", '', 'A green workflow does not imply PASS when this result is NOT_RUN or OS_DENIED.', '', 'Opening via launcher and actual user input remain NOT_RUN.') | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding utf8
    }
}
if ($result.status -eq 'FAIL') { throw "Browser window smoke failed: $($result.error)" }
