#!/bin/bash
# GitHub Actions Setup Verification Script
# Run this after pushing to verify everything is configured correctly

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  GitHub Actions Docker CI/CD Setup Verification Script    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo

# Check Docker
echo "✓ Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "✗ Docker not found. Please install Docker Desktop."
    exit 1
fi
DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
echo "  Docker version: $DOCKER_VERSION"
echo

# Check Docker Compose
echo "✓ Checking Docker Compose installation..."
if ! docker compose version &> /dev/null; then
    echo "✗ Docker Compose not found. Please update Docker Desktop."
    exit 1
fi
echo "  Docker Compose: $(docker compose version --short)"
echo

# Validate Dockerfile
echo "✓ Validating Dockerfile.ui..."
if ! docker build -f Dockerfile.ui --tag bago-portfolio:verify --quiet . &> /dev/null; then
    echo "✗ Dockerfile.ui failed to build. Check for syntax errors."
    exit 1
fi
IMAGE_SIZE=$(docker images bago-portfolio:verify --format "{{.Size}}")
echo "  Image size: $IMAGE_SIZE"
docker rmi bago-portfolio:verify > /dev/null
echo

# Validate Compose files
echo "✓ Validating docker-compose files..."
if ! docker compose -f docker-compose.ui.yml config --quiet 2>/dev/null; then
    echo "✗ docker-compose.ui.yml validation failed."
    exit 1
fi
echo "  docker-compose.ui.yml: ✓"

if ! docker compose -f infra/openmetadata/docker-compose.yml config --quiet 2>/dev/null; then
    echo "✗ infra/openmetadata/docker-compose.yml validation failed."
    exit 1
fi
echo "  infra/openmetadata/docker-compose.yml: ✓"

if ! docker compose -f infra/observability/docker-compose.yml config --quiet 2>/dev/null; then
    echo "✗ infra/observability/docker-compose.yml validation failed."
    exit 1
fi
echo "  infra/observability/docker-compose.yml: ✓"
echo

# Check workflows
echo "✓ Checking GitHub Actions workflows..."
WORKFLOWS=".github/workflows/docker-build.yml .github/workflows/docker-compose-validate.yml .github/workflows/ci.yml"
for workflow in $WORKFLOWS; do
    if [ ! -f "$workflow" ]; then
        echo "✗ Missing workflow: $workflow"
        exit 1
    fi
    echo "  $workflow: ✓"
done
echo

# Check documentation
echo "✓ Checking documentation files..."
DOCS="docs/GITHUB_ACTIONS_QUICKSTART.md docs/github-actions-docker-setup.md docs/docker-hub-secrets-setup.md docs/docker-actions-verification-checklist.md"
for doc in $DOCS; do
    if [ ! -f "$doc" ]; then
        echo "⚠ Missing documentation: $doc"
    else
        echo "  $doc: ✓"
    fi
done
echo

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✓ All local checks passed!                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo
echo "Next steps:"
echo "1. Verify GitHub Actions permissions:"
echo "   → Go to Repository → Settings → Actions → General"
echo "   → Enable 'Read and write permissions'"
echo "   → Save"
echo
echo "2. Push to main branch:"
echo "   → git add ."
echo "   → git commit -m 'chore: add Docker CI/CD workflows'"
echo "   → git push origin main"
echo
echo "3. Monitor the build:"
echo "   → Go to Actions tab"
echo "   → Click 'Docker Build and Push'"
echo "   → Watch the workflow run (5-10 minutes)"
echo
echo "4. Verify image:"
echo "   → Check Packages section on your repo"
echo "   → Should see 'bago_agentic_data_lab' package"
echo "   → Tags should include 'main' and 'sha-xxxxx'"
echo
echo "For detailed help, see docs/GITHUB_ACTIONS_QUICKSTART.md"
