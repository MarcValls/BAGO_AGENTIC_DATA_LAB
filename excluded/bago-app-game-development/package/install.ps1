[CmdletBinding()]
param(
    [string]$CodexHome
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $CodexHome) {
    if ($env:CODEX_HOME) {
        $CodexHome = $env:CODEX_HOME
    } elseif ($env:USERPROFILE) {
        $CodexHome = Join-Path $env:USERPROFILE '.codex'
    } else {
        throw 'Indica -CodexHome o define CODEX_HOME/USERPROFILE.'
    }
}

$source = Join-Path $PSScriptRoot 'skills\bago-app-game-development'
$distributionSource = Join-Path $PSScriptRoot 'package\skills\bago-app-game-development'
if (Test-Path -LiteralPath (Join-Path $distributionSource 'SKILL.md') -PathType Leaf) {
    $source = $distributionSource
}
$skillsRoot = Join-Path $CodexHome 'skills'
$target = Join-Path $skillsRoot 'bago-app-game-development'

if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) {
    throw "No se encuentra la skill del paquete: $source"
}
if (Test-Path -LiteralPath $target) {
    throw "Ya existe la skill de destino; no se sobrescribió: $target"
}

New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
$staging = Join-Path $skillsRoot ('.bago-app-game-development-' + [guid]::NewGuid().ToString('N'))
try {
    Copy-Item -LiteralPath $source -Destination $staging -Recurse
    if (Test-Path -LiteralPath $target) {
        throw "La ruta de destino apareció durante la instalación; no se sobrescribió: $target"
    }
    Move-Item -LiteralPath $staging -Destination $target
} finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}

Write-Output "Skill instalada en: $target"
