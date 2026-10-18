# GitHub Actions Setup Verification Script (PowerShell)
# Run this after pushing to verify everything is configured correctly

$ErrorActionPreference = "Stop"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  GitHub Actions Docker CI/CD Setup Verification Script    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host

# Check Docker
Write-Host "✓ Checking Docker installation..." -ForegroundColor Green
try {
    $dockerVersion = & docker --version | Select-String -Pattern "version" | ForEach-Object { $_.ToString() }
    Write-Host "  Docker: $dockerVersion" -ForegroundColor Gray
}
catch {
    Write-Host "✗ Docker not found. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check Docker Compose
Write-Host "✓ Checking Docker Compose..." -ForegroundColor Green
try {
    $composeVersion = & docker compose version --short
    Write-Host "  Docker Compose: $composeVersion" -ForegroundColor Gray
}
catch {
    Write-Host "✗ Docker Compose not found. Please update Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host

# Validate Dockerfile
Write-Host "✓ Validating Dockerfile.ui..." -ForegroundColor Green
try {
    $buildOutput = & docker build -f Dockerfile.ui --tag bago-portfolio:verify --quiet . 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed"
    }
    $imageSize = & docker images bago-portfolio:verify --format "{{.Size}}" | Select-Object -First 1
    Write-Host "  Image size: $imageSize" -ForegroundColor Gray
    & docker rmi bago-portfolio:verify --quiet | Out-Null
}
catch {
    Write-Host "✗ Dockerfile.ui failed to build. Check for syntax errors." -ForegroundColor Red
    exit 1
}
Write-Host

# Validate Compose files
Write-Host "✓ Validating docker-compose files..." -ForegroundColor Green

$composeFiles = @(
    "docker-compose.ui.yml",
    "infra/openmetadata/docker-compose.yml",
    "infra/observability/docker-compose.yml"
)

foreach ($file in $composeFiles) {
    try {
        $configOutput = & docker compose -f $file config --quiet 2>&1
        Write-Host "  $file : ✓" -ForegroundColor Gray
    }
    catch {
        Write-Host "✗ $file validation failed." -ForegroundColor Red
        exit 1
    }
}
Write-Host

# Check workflows
Write-Host "✓ Checking GitHub Actions workflows..." -ForegroundColor Green
$workflows = @(
    ".github/workflows/docker-build.yml",
    ".github/workflows/docker-compose-validate.yml",
    ".github/workflows/ci.yml"
)

foreach ($workflow in $workflows) {
    if (Test-Path $workflow) {
        Write-Host "  $workflow : ✓" -ForegroundColor Gray
    }
    else {
        Write-Host "✗ Missing workflow: $workflow" -ForegroundColor Red
        exit 1
    }
}
Write-Host

# Check documentation
Write-Host "✓ Checking documentation files..." -ForegroundColor Green
$docs = @(
    "docs/GITHUB_ACTIONS_QUICKSTART.md",
    "docs/github-actions-docker-setup.md",
    "docs/docker-hub-secrets-setup.md",
    "docs/docker-actions-verification-checklist.md"
)

foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Write-Host "  $doc : ✓" -ForegroundColor Gray
    }
    else {
        Write-Host "⚠ Missing documentation: $doc" -ForegroundColor Yellow
    }
}
Write-Host

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  ✓ All local checks passed!                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Verify GitHub Actions permissions:" -ForegroundColor White
Write-Host "   → Go to Repository → Settings → Actions → General" -ForegroundColor Gray
Write-Host "   → Enable 'Read and write permissions'" -ForegroundColor Gray
Write-Host "   → Save" -ForegroundColor Gray
Write-Host

Write-Host "2. Push to main branch:" -ForegroundColor White
Write-Host "   → git add ." -ForegroundColor Gray
Write-Host "   → git commit -m 'chore: add Docker CI/CD workflows'" -ForegroundColor Gray
Write-Host "   → git push origin main" -ForegroundColor Gray
Write-Host

Write-Host "3. Monitor the build:" -ForegroundColor White
Write-Host "   → Go to Actions tab" -ForegroundColor Gray
Write-Host "   → Click 'Docker Build and Push'" -ForegroundColor Gray
Write-Host "   → Watch the workflow run (5-10 minutes)" -ForegroundColor Gray
Write-Host

Write-Host "4. Verify image:" -ForegroundColor White
Write-Host "   → Check Packages section on your repo" -ForegroundColor Gray
Write-Host "   → Should see 'bago_agentic_data_lab' package" -ForegroundColor Gray
Write-Host "   → Tags should include 'main' and 'sha-xxxxx'" -ForegroundColor Gray
Write-Host

Write-Host "For detailed help, see: docs/GITHUB_ACTIONS_QUICKSTART.md" -ForegroundColor Green
