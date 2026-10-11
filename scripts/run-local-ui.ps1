$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw 'Python was not found. Install Python 3.11 or create .venv in the repository.'
    }
    $pythonExe = $pythonCommand.Source
}

$nodeModules = Join-Path $repoRoot 'frontend\node_modules'
if (-not (Test-Path -LiteralPath $nodeModules)) {
    throw 'Frontend packages are missing. Run npm ci in the frontend directory first.'
}

Push-Location (Join-Path $repoRoot 'frontend')
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally {
    Pop-Location
}

& $pythonExe -c 'import fastapi, uvicorn, keyring, requests' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Python UI dependencies are missing. Activate the intended environment and run: python -m pip install -r requirements.txt fastapi uvicorn"
}

function Get-ListenerProcessIds([int]$Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-LocalPortAvailable([int]$Port) {
    if ((Get-ListenerProcessIds $Port).Count -gt 0) { return $false }
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $probe.Start()
        return $true
    } catch {
        return $false
    } finally {
        $probe.Stop()
    }
}

$stateDirectory = Join-Path $env:LOCALAPPDATA 'BAGO\AgentChat\instances'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$pathHash = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($repoRoot.ToLowerInvariant()))).Substring(0, 16).ToLowerInvariant()
$instanceFile = Join-Path $stateDirectory "$pathHash.json"
$previousInstance = $null
if (Test-Path -LiteralPath $instanceFile) {
    try { $previousInstance = Get-Content -LiteralPath $instanceFile -Raw | ConvertFrom-Json } catch { $previousInstance = $null }
    if (-not $previousInstance.listener_pid -or -not $previousInstance.launcher_pid) { $previousInstance = $null }
}

function ConvertTo-UtcRoundTrip([object]$Value) {
    if (-not $Value) { return '' }
    return ([DateTime]$Value).ToUniversalTime().ToString('o')
}

# Stop only the recorded listener process for this checkout. Windows Python venv launchers
# can create a second Python process, so the launcher PID alone does not own the socket.
if ($previousInstance -and $previousInstance.repo_root -eq $repoRoot -and $previousInstance.managed_by -eq 'bago-agent-chat-launcher') {
    $listenerProcess = Get-Process -Id ([int]$previousInstance.listener_pid) -ErrorAction SilentlyContinue
    $listenerInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$previousInstance.listener_pid)" -ErrorAction SilentlyContinue
    if ($previousInstance.listener_pid) {
        $listenerProcess = Get-Process -Id ([int]$previousInstance.listener_pid) -ErrorAction SilentlyContinue
        $listenerInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$previousInstance.listener_pid)" -ErrorAction SilentlyContinue
    } else {
        $listenerProcess = $null
        $listenerInfo = $null
    }
    if (
        $listenerProcess -and $listenerInfo -and
        (ConvertTo-UtcRoundTrip $listenerProcess.StartTime) -eq (ConvertTo-UtcRoundTrip $previousInstance.listener_start_utc) -and
        $listenerInfo.CommandLine -match ' -m src\.api\.server(?:\s|$)'
    ) {
        Stop-Process -Id $listenerProcess.Id -Force
        $listenerProcess.WaitForExit(10000) | Out-Null
    }
    $launcherProcess = Get-Process -Id ([int]$previousInstance.launcher_pid) -ErrorAction SilentlyContinue
    if (
        $launcherProcess -and $previousInstance.launcher_start_utc -and
        (ConvertTo-UtcRoundTrip $launcherProcess.StartTime) -eq (ConvertTo-UtcRoundTrip $previousInstance.launcher_start_utc) -and
        $launcherProcess.Path -eq $pythonExe
    ) {
        Stop-Process -Id $launcherProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

$basePort = 8080
$port = $basePort
while ($port -le 9000 -and -not (Test-LocalPortAvailable $port)) { $port++ }
if ($port -gt 9000) { throw 'No free local port was found in the range 8080-9000.' }

$logDirectory = Join-Path $env:LOCALAPPDATA 'BAGO\AgentChat\logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stdoutLog = Join-Path $logDirectory 'api.stdout.log'
$stderrLog = Join-Path $logDirectory 'api.stderr.log'
$previousApiHost = $env:BAGO_API_HOST
$previousRuntimeMode = $env:BAGO_RUNTIME_MODE
$previousApiPort = $env:BAGO_API_PORT
$previousCorsOrigins = $env:BAGO_CORS_ORIGINS
$env:BAGO_API_HOST = '127.0.0.1'
$env:BAGO_RUNTIME_MODE = 'host'
$env:BAGO_API_PORT = "$port"
$env:BAGO_CORS_ORIGINS = "http://localhost:$port,http://127.0.0.1:$port,http://localhost:5173,http://127.0.0.1:5173"
try {
    $server = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'src.api.server') -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
} finally {
    $env:BAGO_API_HOST = $previousApiHost
    $env:BAGO_RUNTIME_MODE = $previousRuntimeMode
    $env:BAGO_API_PORT = $previousApiPort
    $env:BAGO_CORS_ORIGINS = $previousCorsOrigins
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($server.HasExited) { break }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 1
        if ($health.status -eq 'ok') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Remove-Item -LiteralPath $instanceFile -Force -ErrorAction SilentlyContinue
    throw "Agent Chat API did not become healthy. Check logs: $stderrLog"
}

$listenerIds = Get-ListenerProcessIds $port
if ($listenerIds.Count -ne 1) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "Expected one API listener on port $port; found $($listenerIds.Count)."
}
$listenerPid = [int]$listenerIds[0]
$listenerProcess = Get-Process -Id $listenerPid
$listenerInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid"
if ($listenerInfo.CommandLine -notmatch ' -m src\.api\.server(?:\s|$)') {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "The listener on port $port is not the BAGO Agent Chat server."
}
$instanceState = [ordered]@{
    managed_by = 'bago-agent-chat-launcher'
    repo_root = $repoRoot
    launcher_pid = $server.Id
    launcher_start_utc = $server.StartTime.ToUniversalTime().ToString('o')
    listener_pid = $listenerPid
    listener_start_utc = $listenerProcess.StartTime.ToUniversalTime().ToString('o')
    port = $port
    url = "http://127.0.0.1:$port"
}
$temporaryState = "$instanceFile.tmp"
$instanceState | ConvertTo-Json | Set-Content -LiteralPath $temporaryState -Encoding utf8
Move-Item -LiteralPath $temporaryState -Destination $instanceFile -Force

$url = "http://127.0.0.1:$port"
Write-Output "Agent Chat UI started at $url (PID $($server.Id))."
Write-Output "Logs: $logDirectory"
Start-Process $url
