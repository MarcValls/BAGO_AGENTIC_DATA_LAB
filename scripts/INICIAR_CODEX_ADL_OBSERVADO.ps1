# Run a NEW Codex CLI session with ADL observation. No global config changes.
# The sidecar is stopped on Codex exit; existing monitors or Jaeger are untouched.
param([string[]]$CodexArgs = @())
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$observer = Join-Path $PSScriptRoot 'codex_activity.py'
$python = (Get-Command python -ErrorAction Stop).Source
$codex = (Get-Command codex -ErrorAction Stop).Source
$health = 'http://127.0.0.1:4319/health'
try {
    Invoke-RestMethod -Uri $health -TimeoutSec 1 | Out-Null
    throw 'Port 4319 already serves a process. Refusing to attach to an unverified listener.'
} catch {
    if ($_.Exception.Message -like '*Refusing to attach*') { throw }
}
$logs = Join-Path $env:TEMP 'adl-codex-observer'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stdout = Join-Path $logs 'observer-stdout.log'
$stderr = Join-Path $logs 'observer-stderr.log'
$sidecar = Start-Process -FilePath $python -ArgumentList @("`"$observer`"", 'serve') -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 125
        if ($sidecar.HasExited) { break }
        try {
            $response = Invoke-RestMethod -Uri $health -TimeoutSec 1
            if ($response.status -eq 'READY') { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) { throw "ADL observer not ready; inspect $stderr" }
    Write-Host 'ADL observer READY. Jaeger projection depends on the existing local service.'
    $config = @(
        '-c', 'otel.environment="adl-development"',
        '-c', 'otel.log_user_prompt=false',
        '-c', 'otel.exporter={ otlp-http = { endpoint = "http://127.0.0.1:4319/v1/logs", protocol = "binary" } }',
        '-c', 'otel.trace_exporter={ otlp-http = { endpoint = "http://127.0.0.1:4318/v1/traces", protocol = "binary" } }'
    )
    Push-Location $repo
    try { & $codex @config @CodexArgs }
    finally { Pop-Location }
} finally {
    if ($sidecar -and -not $sidecar.HasExited) {
        Stop-Process -Id $sidecar.Id -ErrorAction SilentlyContinue
    }
    & $python $observer report
}
