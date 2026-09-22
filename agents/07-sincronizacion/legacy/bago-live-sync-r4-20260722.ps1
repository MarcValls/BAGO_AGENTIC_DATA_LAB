[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StageRoot = "C:\tmp\bago-runtime-staging-codex-20260722-r4\current"
$PackageZip = "C:\tmp\bago-runtime-staging-codex-20260722-r4\bago-v4.8.1.zip"
$ManifestPath = "C:\tmp\bago-runtime-staging-codex-20260722-r4\bago-v4.8.1.zip.manifest.json"
$InstallRoot = "C:\Program Files\BAGO"
$RunRoot = "C:\tmp\bago-live-sync-r4-20260722"
$BackupRoot = "C:\ProgramData\BAGO\backups\consolidation-r4-20260722"
$Installer = Join-Path $StageRoot "install-v4.ps1"
$Rollback = Join-Path $StageRoot "rollback-v4.ps1"
$ResultPath = Join-Path $RunRoot "install-result.json"
$BeforePath = Join-Path $RunRoot "state-before.json"
$AfterPath = Join-Path $RunRoot "state-after.json"
$SummaryPath = Join-Path $RunRoot "sync-summary.json"
$PreserveRoot = Join-Path $RunRoot "preserved-runtime-state"
$SafetyArchive = Join-Path $RunRoot "bago-programfiles-before.zip"

function Assert-Administrator {
    $principal = [Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "La sincronizacion requiere PowerShell elevada."
    }
}

function Write-JsonEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Value
    )
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
}

function Get-TreeFingerprint {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [bool]$HashContent = $true
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{
            exists = $false
            type = "missing"
            files = 0
            directories = 0
            bytes = 0
            sha256 = ""
        }
    }

    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) {
        $signature = if ($HashContent) {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
        } else {
            "{0}|{1}" -f $item.Length, $item.LastWriteTimeUtc.Ticks
        }
        return [ordered]@{
            exists = $true
            type = "file"
            files = 1
            directories = 0
            bytes = [int64]$item.Length
            sha256 = $signature
        }
    }

    $root = $item.FullName.TrimEnd("\")
    $directories = @(Get-ChildItem -LiteralPath $root -Force -Recurse -Directory | Sort-Object FullName)
    $files = @(Get-ChildItem -LiteralPath $root -Force -Recurse -File | Sort-Object FullName)
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($directory in $directories) {
        $relative = $directory.FullName.Substring($root.Length + 1).Replace("\", "/")
        $lines.Add("D|$relative")
    }
    [int64]$bytes = 0
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($root.Length + 1).Replace("\", "/")
        $bytes += [int64]$file.Length
        $signature = if ($HashContent) {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
        } else {
            "{0}|{1}" -f $file.Length, $file.LastWriteTimeUtc.Ticks
        }
        $lines.Add("F|$relative|$signature")
    }
    $payload = [Text.Encoding]::UTF8.GetBytes([string]::Join("`n", $lines))
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = [Convert]::ToHexString($sha.ComputeHash($payload)).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    return [ordered]@{
        exists = $true
        type = "directory"
        files = $files.Count
        directories = $directories.Count
        bytes = $bytes
        sha256 = $digest
    }
}

function Get-StateSnapshot {
    return [pscustomobject][ordered]@{
        runtime_gabo = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".gabo") -HashContent $true
        runtime_state = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\state") -HashContent $true
        runtime_logs = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\logs") -HashContent $true
        runtime_context = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\context") -HashContent $true
        runtime_link = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\link.json") -HashContent $true
        runtime_pack = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\pack.json") -HashContent $true
        install_config = Get-TreeFingerprint -Path (Join-Path $InstallRoot "install_config.json") -HashContent $true
        runtime_config = Get-TreeFingerprint -Path (Join-Path $InstallRoot ".bago\config.json") -HashContent $true
        localappdata_state = Get-TreeFingerprint -Path (Join-Path $env:LOCALAPPDATA "BAGO") -HashContent $false
        legacy_user_state = Get-TreeFingerprint -Path (Join-Path $env:USERPROFILE ".bago") -HashContent $false
        programdata_user_state = Get-TreeFingerprint -Path (Join-Path $env:ProgramData "BAGO\user") -HashContent $false
        localappdata_selection = Get-TreeFingerprint -Path (Join-Path $env:LOCALAPPDATA "BAGO\install_selection.json") -HashContent $true
        legacy_selection = Get-TreeFingerprint -Path (Join-Path $env:USERPROFILE ".bago\install_selection.json") -HashContent $true
        programdata_selection = Get-TreeFingerprint -Path (Join-Path $env:ProgramData "BAGO\user\install_selection.json") -HashContent $true
    }
}

function Compare-StateSnapshots {
    param(
        [Parameter(Mandatory = $true)][object]$Before,
        [Parameter(Mandatory = $true)][object]$After
    )
    $mismatches = [Collections.Generic.List[string]]::new()
    foreach ($property in $Before.PSObject.Properties) {
        $name = $property.Name
        $beforeJson = $property.Value | ConvertTo-Json -Compress
        $afterJson = $After.$name | ConvertTo-Json -Compress
        if ($beforeJson -ne $afterJson) {
            $mismatches.Add($name)
        }
    }
    return @($mismatches)
}

function Copy-PreservedPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $source = Join-Path $InstallRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) { return }
    $target = Join-Path $PreserveRoot $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

function Restore-PreservedPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $source = Join-Path $PreserveRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) { return }
    $target = Join-Path $InstallRoot $RelativePath
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

function Invoke-SafeRollback {
    param([string]$BackupZip)
    if ([string]::IsNullOrWhiteSpace($BackupZip) -or -not (Test-Path -LiteralPath $BackupZip -PathType Leaf)) {
        return $false
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Rollback `
        -BackupZip $BackupZip `
        -InstallDir $InstallRoot `
        -BackupRoot $BackupRoot `
        -RestoreBackedUpState `
        -SkipTests
    if ($LASTEXITCODE -ne 0) {
        throw "Rollback automatico fallido: $LASTEXITCODE"
    }
    foreach ($relative in @(".gabo", ".bago\state", ".bago\logs", ".bago\context", ".bago\link.json", ".bago\pack.json", "install_config.json", ".bago\config.json")) {
        Restore-PreservedPath -RelativePath $relative
    }
    return $true
}

Assert-Administrator

foreach ($required in @($StageRoot, $PackageZip, $ManifestPath, $Installer, $Rollback, $InstallRoot, $SafetyArchive)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Precondicion ausente: $required"
    }
}
if (Test-Path -LiteralPath $ResultPath) {
    throw "Ya existe resultado de una ejecucion previa: $ResultPath"
}
if (Test-Path -LiteralPath $PreserveRoot) {
    throw "Ya existe el area de preservacion: $PreserveRoot"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$packageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PackageZip).Hash.ToLowerInvariant()
if ($packageHash -ne ([string]$manifest.zip_sha256).ToLowerInvariant()) {
    throw "Hash r4 invalido: $packageHash"
}
if ([int]$manifest.file_count -ne 614) {
    throw "Manifiesto r4 inesperado: $($manifest.file_count) archivos"
}
$safetyHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SafetyArchive).Hash.ToLowerInvariant()
if ($safetyHash -ne "ef5b23a2338c99e4f37f2f3c972e95bc3f08fb528c35dbac086705c06919f463") {
    throw "El backup de seguridad previo cambio: $safetyHash"
}

New-Item -ItemType Directory -Path $PreserveRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RunRoot "temp") -Force | Out-Null
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

$before = Get-StateSnapshot
Write-JsonEvidence -Path $BeforePath -Value $before

foreach ($relative in @(".gabo", ".bago\state", ".bago\logs", ".bago\context", ".bago\link.json", ".bago\pack.json", "install_config.json", ".bago\config.json")) {
    Copy-PreservedPath -RelativePath $relative
}

$preservedCheck = [ordered]@{
    runtime_gabo = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".gabo") -HashContent $true
    runtime_state = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\state") -HashContent $true
    runtime_logs = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\logs") -HashContent $true
    runtime_context = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\context") -HashContent $true
    runtime_link = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\link.json") -HashContent $true
    runtime_pack = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\pack.json") -HashContent $true
    install_config = Get-TreeFingerprint -Path (Join-Path $PreserveRoot "install_config.json") -HashContent $true
    runtime_config = Get-TreeFingerprint -Path (Join-Path $PreserveRoot ".bago\config.json") -HashContent $true
}
foreach ($name in $preservedCheck.Keys) {
    $left = $before.$name | ConvertTo-Json -Compress
    $right = $preservedCheck[$name] | ConvertTo-Json -Compress
    if ($left -ne $right) {
        throw "Copia de preservacion no coincide: $name"
    }
}

$env:BAGO_USER_ROOT = Join-Path $RunRoot "boundary\user"
$env:BAGO_USER_HOME = $env:BAGO_USER_ROOT
$env:BAGO_LEGACY_USER_ROOT = $env:BAGO_USER_ROOT
$env:BAGO_STATE_ROOT = Join-Path $RunRoot "boundary\state"
$env:BAGO_DATA_ROOT = Join-Path $RunRoot "boundary\data"
$env:BAGO_MANAGER_BASE_PATH = Join-Path $RunRoot "boundary\workspace"
$env:BAGO_CREDENTIALS_MODE = "session"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:TEMP = Join-Path $RunRoot "temp"
$env:TMP = $env:TEMP

$backupZip = ""
$rolledBack = $false
try {
    $installOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer `
        -PackageZip $PackageZip `
        -InstallDir $InstallRoot `
        -BackupRoot $BackupRoot `
        -UserStateDir (Join-Path $RunRoot "boundary\installer-user") `
        -Mode Express `
        -SkipTests `
        -NoPathUpdate `
        -NoShellIntegration `
        -ElevatedChild `
        -ResultPath $ResultPath 2>&1
    [IO.File]::WriteAllLines((Join-Path $RunRoot "install-output.log"), [string[]]$installOutput, [Text.UTF8Encoding]::new($false))
    if ($LASTEXITCODE -ne 0) {
        throw "Instalacion fallida: $LASTEXITCODE"
    }
    if (($installOutput -join "`n") -match "No se pudo limpiar") {
        throw "El instalador no pudo limpiar por completo el runtime anterior"
    }
    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        throw "El instalador no genero install-result.json"
    }
    $result = Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $backupZip = [string]$result.backup_zip
    if (-not (Test-Path -LiteralPath $backupZip -PathType Leaf)) {
        throw "Backup del instalador ausente: $backupZip"
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $backupArchive = [IO.Compression.ZipFile]::OpenRead($backupZip)
    try {
        $backupEntries = @($backupArchive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    } finally {
        $backupArchive.Dispose()
    }
    $requiredBackupEntries = @(
        ".gabo/workspace.json",
        ".bago/state/context.json",
        ".bago/context/context-tree.json",
        ".bago/link.json",
        ".bago/pack.json",
        "install_config.json",
        ".bago/config.json"
    )
    $missingBackupEntries = @($requiredBackupEntries | Where-Object { $_ -notin $backupEntries })
    if ($missingBackupEntries.Count -gt 0) {
        throw "Backup incompleto: $($missingBackupEntries -join ', ')"
    }

    $runtimeGabo = Join-Path $InstallRoot ".gabo"
    if (Test-Path -LiteralPath $runtimeGabo) {
        throw "El release r4 contiene un .gabo inesperado"
    }
    Restore-PreservedPath -RelativePath ".gabo"
    Restore-PreservedPath -RelativePath ".bago\context"
    Restore-PreservedPath -RelativePath ".bago\link.json"
    Restore-PreservedPath -RelativePath ".bago\pack.json"

    $after = Get-StateSnapshot
    Write-JsonEvidence -Path $AfterPath -Value $after
    $stateMismatches = @(Compare-StateSnapshots -Before $before -After $after)
    if ($stateMismatches.Count -gt 0) {
        throw "Estado divergente tras sync: $($stateMismatches -join ', ')"
    }

    $summary = [ordered]@{
        ok = $true
        installed_to = $InstallRoot
        package = $PackageZip
        package_sha256 = $packageHash
        manifest_files = [int]$manifest.file_count
        backup_zip = $backupZip
        backup_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $backupZip).Hash.ToLowerInvariant()
        safety_archive = $SafetyArchive
        safety_archive_sha256 = $safetyHash
        state_migrated = $false
        state_mismatches = @()
        shell_integration = $false
        rolled_back = $false
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
    }
    Write-JsonEvidence -Path $SummaryPath -Value $summary
    $summary | ConvertTo-Json -Depth 8
} catch {
    $failure = $_
    if ([string]::IsNullOrWhiteSpace($backupZip)) {
        $candidate = Get-ChildItem -LiteralPath $BackupRoot -Filter "bago-programfiles-backup-*.zip" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($candidate) { $backupZip = $candidate.FullName }
    }
    if ($backupZip) {
        $rolledBack = Invoke-SafeRollback -BackupZip $backupZip
    }
    $rollbackSnapshot = Get-StateSnapshot
    $rollbackMismatches = @(Compare-StateSnapshots -Before $before -After $rollbackSnapshot)
    Write-JsonEvidence -Path (Join-Path $RunRoot "sync-failure.json") -Value ([ordered]@{
        ok = $false
        error = $failure.Exception.Message
        backup_zip = $backupZip
        rolled_back = $rolledBack
        rollback_state_mismatches = $rollbackMismatches
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
    })
    throw $failure
}
