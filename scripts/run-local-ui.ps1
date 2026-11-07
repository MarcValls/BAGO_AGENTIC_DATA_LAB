param([switch]$PreflightOnly, [switch]$InspectWindowsOnly)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Get-VisibleBrowserWindows {
    $browserNames = @('brave', 'chrome', 'msedge', 'firefox', 'vivaldi', 'opera', 'opera_gx', 'chromium')
    $windows = @()
    foreach ($browserName in $browserNames) {
        foreach ($process in @(Get-Process -Name $browserName -ErrorAction SilentlyContinue)) {
            if ($process.MainWindowHandle -eq [IntPtr]::Zero) { continue }
            $windows += [pscustomobject]@{
                ProcessId = [int]$process.Id
                ProcessName = [string]$process.ProcessName
                Title = [string]$process.MainWindowTitle
                Handle = [IntPtr]$process.MainWindowHandle
                AddressState = Get-VisibleBrowserAddressState ([IntPtr]$process.MainWindowHandle)
            }
        }
    }
    return @($windows | Sort-Object ProcessId -Unique)
}

function Test-LocalUiAddress([string]$Value) {
    return $Value -match '(?i)^(?:http://)?(?:127\.0\.0\.1|localhost):8080(?:[/?#]|$)'
}

function Get-VisibleBrowserAddressState([IntPtr]$Handle) {
    try {
        Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
        $window = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
        if (-not $window) { return 'UNKNOWN' }
        $condition = [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Edit)
        $edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        $states = @()
        foreach ($edit in $edits) {
            if ($edit.Current.IsOffscreen) { continue }
            $name = [string]$edit.Current.Name
            $id = [string]$edit.Current.AutomationId
            if ($name -notmatch '(?i)address.*search|search.*address|address bar|direcci[oó]n.*b[uú]squeda|barra de direcciones' -and
                $id -notmatch '(?i)^(?:address|omnibox)') { continue }
            $pattern = $null
            if ($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                if (Test-LocalUiAddress ([string]$pattern.Current.Value)) { $states += 'MATCH' }
                else { $states += 'OTHER' }
            }
        }
        if ($states.Count -eq 1) { return $states[0] }
    } catch { return 'UNKNOWN' }
    return 'UNKNOWN'
}

function Resolve-BrowserWindowAction {
    $windows = @(Get-VisibleBrowserWindows)
    $bagoWindows = @($windows | Where-Object { $_.AddressState -eq 'MATCH' })
    if ($windows.Count -eq 0) {
        return [pscustomobject]@{ Action = 'launch'; Window = $null; BagoRecognized = $false }
    }
    if ($bagoWindows.Count -eq 1) {
        return [pscustomobject]@{ Action = 'focus'; Window = $bagoWindows[0]; BagoRecognized = $true }
    }
    $candidates = $windows
    if ($bagoWindows.Count -gt 0) {
        Write-Host 'La barra de alguna ventana contiene la direccion local; confirma el PID que quieres reutilizar:'
    } else {
        Write-Host 'Hay ventanas de navegador, pero no puedo confirmar cuál tiene BAGO activa.'
        Write-Host 'Indica el PID de la ventana donde ya está abierta BAGO. No abriré otra pestaña.'
    }

    foreach ($candidate in $candidates) {
        $title = if ([string]::IsNullOrWhiteSpace($candidate.Title)) { '(sin título)' } else { $candidate.Title }
        $hint = if ($candidate.AddressState -eq 'MATCH') { ' [barra coincide]' } else { '' }
        Write-Host ('  PID {0}  {1}  {2}{3}' -f $candidate.ProcessId, $candidate.ProcessName, $title, $hint)
    }
    try {
        $selectedPidText = Read-Host 'PID (Intro para no abrir navegador)'
    } catch {
        Write-Host 'No hay consola interactiva; omito el navegador para evitar abrir otra ventana.'
        return [pscustomobject]@{ Action = 'skip'; Window = $null; BagoRecognized = $false }
    }
    if ([string]::IsNullOrWhiteSpace($selectedPidText)) {
        return [pscustomobject]@{ Action = 'skip'; Window = $null; BagoRecognized = $false }
    }
    $selectedPid = 0
    if (-not [int]::TryParse($selectedPidText.Trim(), [ref]$selectedPid)) {
        throw "PID no válido: '$selectedPidText'. No se abrirá otra ventana del navegador."
    }
    $selectedWindow = @($candidates | Where-Object { $_.ProcessId -eq $selectedPid } | Select-Object -First 1)
    if ($selectedWindow.Count -ne 1) {
        throw "El PID $selectedPid no corresponde a una ventana candidata. No se abrirá otra ventana del navegador."
    }
    return [pscustomobject]@{
        Action = 'focus'
        Window = $selectedWindow[0]
        BagoRecognized = ($selectedWindow[0].AddressState -eq 'MATCH')
    }
}

function Focus-BrowserWindow([object]$Window) {
    $process = Get-Process -Id ([int]$Window.ProcessId) -ErrorAction SilentlyContinue
    if (-not $process -or $process.MainWindowHandle -eq [IntPtr]::Zero -or $process.MainWindowHandle -ne $Window.Handle) {
        Write-Warning "La ventana del navegador PID $($Window.ProcessId) ya no está disponible; no abriré otra."
        return $false
    }
    if (-not ('Bago.LocalUi.WindowApi' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace Bago.LocalUi {
    public static class WindowApi {
        [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    }
}
'@
    }
    [Bago.LocalUi.WindowApi]::ShowWindowAsync($process.MainWindowHandle, 9) | Out-Null
    if (-not [Bago.LocalUi.WindowApi]::SetForegroundWindow($process.MainWindowHandle)) {
        Write-Warning "Windows no permitió enfocar el navegador PID $($Window.ProcessId); no abriré otra ventana."
        return $false
    }
    return $true
}

function Test-LocalUiRuntimeIdentity([object]$Runtime, [string]$ExpectedSource, [int]$OwnerId) {
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $sourceHash = [BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($ExpectedSource))).Replace('-', '')
        } finally {
            $sha.Dispose()
        }
        return ([int]$Runtime.process_id -eq $OwnerId -and $Runtime.server_source_path -and
            [IO.Path]::GetFullPath([string]$Runtime.server_source_path) -ieq [IO.Path]::GetFullPath($ExpectedSource) -and
            [string]$Runtime.server_source_sha256_at_import -ieq $sourceHash)
    } catch {
        return $false
    }
}

function Get-LocalUiInstanceFile {
    $directory = Join-Path $env:LOCALAPPDATA 'BAGO\AgentChat\instances'
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($repoRoot.ToLowerInvariant()))
        $name = ([BitConverter]::ToString($bytes) -replace '-', '').Substring(0, 16).ToLowerInvariant()
    } finally { $hasher.Dispose() }
    return (Join-Path $directory "$name.json")
}

function Get-LocalUiInputFingerprint([string]$Kind) {
    $python = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if (-not $command) { throw 'Python no disponible para comprobar las fuentes.' }
        $python = $command.Source
    }
    $helper = Join-Path $repoRoot 'scripts\runtime_fingerprint.py'
    $output = @(& $python -B $helper --root $repoRoot --kind $Kind)
    if ($LASTEXITCODE -ne 0 -or $output.Count -ne 1 -or $output[0] -notmatch '^[0-9a-f]{64}$') {
        throw "No se pudo comprobar la huella de $Kind."
    }
    return [string]$output[0]
}

function Test-LocalUiFreshnessProof([object]$Proof, [int]$OwnerId, [datetime]$OwnerStart) {
    try {
        if (-not $Proof) { return $false }
        $recordedStart = if ($Proof.listener_start_utc -is [datetime]) {
            if ($Proof.listener_start_utc.Kind -ne [DateTimeKind]::Utc) { return $false }
            $Proof.listener_start_utc.ToUniversalTime()
        } else {
            $text = [string]$Proof.listener_start_utc
            if ($text -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z$') { return $false }
            [datetime]::ParseExact($text, 'o', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        }
        if ($Proof.managed_by -ne 'bago-agent-chat-launcher' -or
            $Proof.fingerprint_version -ne 'bago-runtime-inputs-v1' -or
            [IO.Path]::GetFullPath([string]$Proof.repo_root) -ine [IO.Path]::GetFullPath($repoRoot) -or
            [int]$Proof.listener_pid -ne $OwnerId -or
            $recordedStart -ne $OwnerStart.ToUniversalTime()) { return $false }
        foreach ($kind in @('backend', 'frontend', 'dist')) {
            $recorded = [string]$Proof.input_fingerprints.$kind
            if ($recorded -notmatch '^[0-9a-f]{64}$' -or (Get-LocalUiInputFingerprint $kind) -cne $recorded) { return $false }
        }
        return $true
    } catch { return $false }
}

function Enter-LocalUiStartLock([string]$Name = 'Local\BAGO_ADL_UI_8080') {
    $mutex = [System.Threading.Mutex]::new($false, $Name)
    try {
        try { $acquired = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { $mutex.Dispose(); return $null }
        return $mutex
    } catch {
        $mutex.Dispose()
        throw
    }
}

function Get-LocalUiPreflight([object]$PendingProof = $null) {
    $allListeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
    $otherListeners = @($allListeners | Where-Object { $_.LocalPort -ne 8080 })
    foreach ($otherId in @($otherListeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $otherProcess = Get-Process -Id ([int]$otherId) -ErrorAction SilentlyContinue
        if (-not $otherProcess -or $otherProcess.ProcessName -notmatch '^(?:python(?:w)?(?:\d+(?:\.\d+)*)?|uvicorn)$') { continue }
        $otherInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$otherId)" -ErrorAction SilentlyContinue
        if ($otherInfo -and $otherInfo.CommandLine -match '(?i)(?:\s-m\s+src\.api\.server(?:\s|$)|\bsrc\.api\.server:app\b)') {
            $otherPorts = @($otherListeners | Where-Object { $_.OwningProcess -eq $otherId } | Select-Object -ExpandProperty LocalPort -Unique)
            return [pscustomobject]@{ State = 'CONFLICT'; Pid = [int]$otherId; Reason = "Otro proceso ADL escucha en puerto(s): $($otherPorts -join ',')." }
        }
    }
    $listeners = @($allListeners | Where-Object { $_.LocalPort -eq 8080 })
    if ($listeners.Count -eq 0) { return [pscustomobject]@{ State = 'FREE'; Pid = $null; Reason = '' } }
    $ids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($ids.Count -ne 1 -or @($listeners | Where-Object { $_.LocalAddress -ne '127.0.0.1' }).Count -gt 0) {
        return [pscustomobject]@{ State = 'CONFLICT'; Pid = ($ids -join ','); Reason = 'Listener ambiguo o no limitado a 127.0.0.1.' }
    }
    $ownerId = [int]$ids[0]
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId" -ErrorAction SilentlyContinue
    if (-not $owner -or $owner.Name -notmatch '^python(?:w)?(?:\d+(?:\.\d+)*)?\.exe$' -or $owner.CommandLine -notmatch '(?i)\s-m\s+src\.api\.server(?:\s|$)') {
        return [pscustomobject]@{ State = 'CONFLICT'; Pid = $ownerId; Reason = 'No se pudo identificar el servidor de este checkout.' }
    }
    Add-Type -AssemblyName System.Net.Http
    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromSeconds(5)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $base = 'http://127.0.0.1:8080'
        $health = ($client.GetStringAsync("$base/api/health").GetAwaiter().GetResult() | ConvertFrom-Json)
        if ($health.status -ne 'ok') { throw 'Health no es ok.' }
        $spec = ($client.GetStringAsync("$base/openapi.json").GetAwaiter().GetResult() | ConvertFrom-Json)
        $routes = @($spec.paths.PSObject.Properties.Name)
        if ('/api/health' -notin $routes -or '/api/providers/selection' -notin $routes -or '/api/runtime/storage' -notin $routes) { throw 'Faltan rutas esperadas.' }
        $runtime = ($client.GetStringAsync("$base/api/runtime/storage").GetAwaiter().GetResult() | ConvertFrom-Json)
        $expectedSource = [IO.Path]::GetFullPath((Join-Path $repoRoot 'src\api\server.py'))
        if (-not (Test-LocalUiRuntimeIdentity $runtime $expectedSource $ownerId)) {
            throw 'El servidor no acredita el PID y las fuentes actuales de este checkout.'
        }
        $proof = $PendingProof
        if (-not $proof) {
            $proofPath = Get-LocalUiInstanceFile
            if (-not (Test-Path -LiteralPath $proofPath -PathType Leaf)) { throw 'Falta el recibo de fuentes de esta instancia.' }
            $proof = Get-Content -Raw -LiteralPath $proofPath | ConvertFrom-Json
        }
        $ownerProcess = Get-Process -Id $ownerId -ErrorAction Stop
        if (-not (Test-LocalUiFreshnessProof $proof $ownerId $ownerProcess.StartTime)) {
            throw 'La instancia no acredita que backend, fuentes frontend y build sigan siendo los registrados al arrancar.'
        }
        $indexPath = Join-Path $repoRoot 'frontend\dist\index.html'
        $indexBytes = [System.IO.File]::ReadAllBytes($indexPath)
        $servedIndex = $client.GetByteArrayAsync("$base/").GetAwaiter().GetResult()
        if ([BitConverter]::ToString($hasher.ComputeHash($indexBytes)) -ne [BitConverter]::ToString($hasher.ComputeHash($servedIndex))) { throw 'El index servido no coincide con frontend/dist.' }
        $html = [Text.Encoding]::UTF8.GetString($indexBytes)
        $matches = [regex]::Matches($html, '(?:src|href)="(/assets/[A-Za-z0-9_.-]+\.(?:js|css))"')
        $paths = @($matches | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
        if (-not ($paths | Where-Object { $_ -like '*.js' }) -or -not ($paths | Where-Object { $_ -like '*.css' })) { throw 'No se identifican los assets JS y CSS.' }
        foreach ($asset in $paths) {
            $file = Join-Path (Join-Path $repoRoot 'frontend\dist') $asset.TrimStart([char]'/').Replace('/', [IO.Path]::DirectorySeparatorChar)
            $local = [System.IO.File]::ReadAllBytes($file)
            $served = $client.GetByteArrayAsync("$base$asset").GetAwaiter().GetResult()
            if ([BitConverter]::ToString($hasher.ComputeHash($local)) -ne [BitConverter]::ToString($hasher.ComputeHash($served))) { throw "El asset $asset no coincide con frontend/dist." }
        }
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId" -ErrorAction SilentlyContinue
        $currentIds = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
        if (-not $current -or $current.CreationDate -ne $owner.CreationDate -or $currentIds.Count -ne 1 -or [int]$currentIds[0] -ne $ownerId) { throw 'El listener cambio durante la comprobacion.' }
        return [pscustomobject]@{ State = 'REUSE'; Pid = $ownerId; Reason = '' }
    } catch {
        return [pscustomobject]@{ State = 'CONFLICT'; Pid = $ownerId; Reason = $_.Exception.Message }
    } finally {
        $hasher.Dispose()
        $client.Dispose()
    }
}

if ($InspectWindowsOnly) {
    @(Get-VisibleBrowserWindows | Select-Object ProcessId, AddressState) | ConvertTo-Json -Compress
    return
}

$preflight = Get-LocalUiPreflight
if ($PreflightOnly) {
    $preflight | ConvertTo-Json -Compress
    if ($preflight.State -eq 'CONFLICT') { exit 2 }
    exit 0
}
if ($preflight.State -eq 'CONFLICT') {
    throw "El puerto 8080 esta ocupado por PID $($preflight.Pid): $($preflight.Reason) No se iniciara otra instancia."
}
if ($preflight.State -eq 'REUSE') {
    Write-Output "Se reutiliza la API existente en http://127.0.0.1:8080 (PID $($preflight.Pid))."
    $browserAction = Resolve-BrowserWindowAction
    if ($browserAction.Action -eq 'focus') {
        if (Focus-BrowserWindow $browserAction.Window) {
            if ($browserAction.BagoRecognized) {
                Write-Output "Ventana seleccionada enfocada (PID $($browserAction.Window.ProcessId)); la barra coincide, pero la navegacion no se ha autenticado."
            } else {
                Write-Output "Ventana seleccionada enfocada (PID $($browserAction.Window.ProcessId)); su URL no se pudo confirmar."
            }
        }
    } elseif ($browserAction.Action -eq 'launch') {
        Start-Process 'http://127.0.0.1:8080'
    } else {
        Write-Output 'Navegador omitido; no se creo ninguna pestana o ventana nueva.'
    }
    return
}

$startLock = Enter-LocalUiStartLock
if (-not $startLock) { throw 'Otro lanzador esta preparando ADL. No se iniciara una segunda instancia.' }
try {
    $lockedPreflight = Get-LocalUiPreflight
    if ($lockedPreflight.State -ne 'FREE') {
        throw 'El puerto 8080 cambio durante el inicio. Ejecuta de nuevo el lanzador para reutilizar la instancia o revisar el conflicto.'
    }

# Detect the existing UI before building or starting anything. A blank PID choice
# intentionally suppresses browser launch; it never creates another tab/window.
$browserAction = Resolve-BrowserWindowAction
if ($browserAction.Action -eq 'focus') {
    Write-Output "Se reutilizará la ventana PID $($browserAction.Window.ProcessId) ($($browserAction.Window.Title))."
} elseif ($browserAction.Action -eq 'skip') {
    Write-Output 'No se abrirá ni enfocará un navegador; la API se puede iniciar igualmente.'
}

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

$frontendBeforeBuild = Get-LocalUiInputFingerprint 'frontend'
Push-Location (Join-Path $repoRoot 'frontend')
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally {
    Pop-Location
}
$frontendFingerprint = Get-LocalUiInputFingerprint 'frontend'
if ($frontendBeforeBuild -cne $frontendFingerprint) { throw 'Las fuentes frontend cambiaron durante el build; no se iniciará ADL.' }
$distFingerprint = Get-LocalUiInputFingerprint 'dist'

& $pythonExe -c 'import fastapi, uvicorn, keyring, requests' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Python UI dependencies are missing. Activate the intended environment and run: python -m pip install -r requirements.txt fastapi uvicorn"
}

function Get-ListenerProcessIds([int]$Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-LocalPortAvailable([int]$Port) {
    if (@(Get-ListenerProcessIds $Port).Count -gt 0) { return $false }
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

$instanceFile = Get-LocalUiInstanceFile
$stateDirectory = Split-Path -Parent $instanceFile
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$port = 8080
if (-not (Test-LocalPortAvailable $port)) {
    throw 'Port 8080 became occupied after preflight. No alternate port or second instance will be started.'
}

$logDirectory = Join-Path $env:LOCALAPPDATA 'BAGO\AgentChat\logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logId = [guid]::NewGuid().ToString('N')
$stdoutLog = Join-Path $logDirectory "api.$logId.stdout.log"
$stderrLog = Join-Path $logDirectory "api.$logId.stderr.log"
$previousApiHost = $env:BAGO_API_HOST
$previousRuntimeMode = $env:BAGO_RUNTIME_MODE
$previousApiPort = $env:BAGO_API_PORT
$previousCorsOrigins = $env:BAGO_CORS_ORIGINS
$previousPyCachePrefix = $env:PYTHONPYCACHEPREFIX
$previousDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE
$backendFingerprint = Get-LocalUiInputFingerprint 'backend'
$env:BAGO_API_HOST = '127.0.0.1'
$env:BAGO_RUNTIME_MODE = 'host'
$env:BAGO_API_PORT = "$port"
$env:BAGO_CORS_ORIGINS = "http://localhost:$port,http://127.0.0.1:$port,http://localhost:5173,http://127.0.0.1:5173"
$env:PYTHONPYCACHEPREFIX = Join-Path $logDirectory ('unused-bytecode-' + [guid]::NewGuid().ToString('N'))
$env:PYTHONDONTWRITEBYTECODE = '1'
try {
    $server = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'src.api.server') -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
} finally {
    $env:BAGO_API_HOST = $previousApiHost
    $env:BAGO_RUNTIME_MODE = $previousRuntimeMode
    $env:BAGO_API_PORT = $previousApiPort
    $env:BAGO_CORS_ORIGINS = $previousCorsOrigins
    $env:PYTHONPYCACHEPREFIX = $previousPyCachePrefix
    $env:PYTHONDONTWRITEBYTECODE = $previousDontWriteBytecode
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
    throw "Agent Chat API did not become healthy. Check logs: $stderrLog"
}

$listenerIds = @(Get-ListenerProcessIds $port)
if ($listenerIds.Count -ne 1) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "Expected one API listener on port $port; found $($listenerIds.Count)."
}
$listenerPid = [int]$listenerIds[0]
$listenerProcess = Get-Process -Id $listenerPid
$listenerInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid"
if ($listenerInfo.CommandLine -notmatch ' -m src\.api\.server(?:\s|$)' -or
    ($listenerPid -ne $server.Id -and [int]$listenerInfo.ParentProcessId -ne $server.Id)) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "The listener on port $port is not the BAGO Agent Chat server."
}
$instanceState = [pscustomobject][ordered]@{
    managed_by = 'bago-agent-chat-launcher'
    repo_root = $repoRoot
    launcher_pid = $server.Id
    launcher_start_utc = $server.StartTime.ToUniversalTime().ToString('o')
    listener_pid = $listenerPid
    listener_start_utc = $listenerProcess.StartTime.ToUniversalTime().ToString('o')
    fingerprint_version = 'bago-runtime-inputs-v1'
    input_fingerprints = [pscustomobject]@{ backend = $backendFingerprint; frontend = $frontendFingerprint; dist = $distFingerprint }
    port = $port
    url = "http://127.0.0.1:$port"
}
$postflight = Get-LocalUiPreflight -PendingProof $instanceState
if ($postflight.State -ne 'REUSE' -or [int]$postflight.Pid -ne $listenerPid) {
    $stillListener = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
    $stillInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid" -ErrorAction SilentlyContinue
    if ($stillListener -and $stillInfo -and $stillListener.StartTime -eq $listenerProcess.StartTime -and
        ($listenerPid -eq $server.Id -or [int]$stillInfo.ParentProcessId -eq $server.Id)) {
        Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
    }
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    throw "The started listener failed identity or asset checks: $($postflight.Reason)"
}
$temporaryState = "$instanceFile.$([guid]::NewGuid().ToString('N')).tmp"
try {
    $instanceState | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporaryState -Encoding utf8
    Move-Item -LiteralPath $temporaryState -Destination $instanceFile -Force
} catch {
    $receiptError = $_.Exception.Message
    $cleanupOk = $true
    try {
        $stillListener = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
        $stillInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid" -ErrorAction SilentlyContinue
        if ($stillListener -and $stillInfo -and $stillListener.StartTime -eq $listenerProcess.StartTime -and
            ($listenerPid -eq $server.Id -or [int]$stillInfo.ParentProcessId -eq $server.Id)) {
            Stop-Process -Id $listenerPid -Force -ErrorAction Stop
        } elseif ($stillListener) { $cleanupOk = $false }
        if ($server.Id -ne $listenerPid) {
            $stillServer = Get-Process -Id $server.Id -ErrorAction SilentlyContinue
            if ($stillServer -and $stillServer.StartTime -eq $server.StartTime) { Stop-Process -Id $server.Id -Force -ErrorAction Stop }
            elseif ($stillServer) { $cleanupOk = $false }
        }
    } catch { $cleanupOk = $false }
    Remove-Item -LiteralPath $temporaryState -Force -ErrorAction SilentlyContinue
    throw "No se pudo guardar el recibo de la instancia PID $listenerPid; limpieza del proceso iniciado: $cleanupOk. $receiptError"
}

$url = "http://127.0.0.1:$port"
Write-Output "Agent Chat UI started at $url (PID $($server.Id))."
Write-Output "Logs: $logDirectory"
if ($browserAction.Action -eq 'launch') {
    # Recheck after startup to avoid a race with a window opened in the meantime.
    $browserAction = Resolve-BrowserWindowAction
}
if ($browserAction.Action -eq 'focus') {
    if (Focus-BrowserWindow $browserAction.Window) {
        Write-Output "Ventana existente enfocada (PID $($browserAction.Window.ProcessId)); no se abrió otra pestaña."
        if ($browserAction.BagoRecognized) {
            Write-Output 'La barra coincide con la direccion local, pero no autentica la navegacion.'
        } else {
            Write-Output 'No pude confirmar la direccion en la barra; enfoque la ventana elegida sin navegar ni cambiar de pestana.'
        }
    }
} elseif ($browserAction.Action -eq 'launch') {
    Start-Process $url
} else {
    Write-Output 'Navegador omitido; no se creó ninguna pestaña o ventana nueva.'
}
} finally {
    $startLock.ReleaseMutex()
    $startLock.Dispose()
}
