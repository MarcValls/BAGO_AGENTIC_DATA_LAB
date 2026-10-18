# GitHub Actions Docker CI/CD Setup for BAGO Agentic Data Lab

## Overview

This project includes three Docker-focused GitHub Actions workflows:

1. **`docker-build.yml`** — Build, push, and scan Docker images
2. **`ci.yml`** — Enhanced CI with Docker Compose health checks
3. **`docker-compose-validate.yml`** — Validate all compose files

---

## Workflows

### docker-build.yml

**Triggers:** Push to main, tags (v*), PRs, manual dispatch

**Features:**
- **Docker Buildx multi-platform support** — Builds for linux/amd64 and can be extended to linux/arm64
- **Registry caching** — Reuses layers from `ghcr.io` (GitHub Container Registry) to speed up builds
- **Automated tagging** — Generates semantic version tags, branch refs, commit SHA
- **Security scanning** — Runs Trivy to detect vulnerabilities
- **Conditional push** — Only pushes on main/tags, not on PR

**Image naming:** `ghcr.io/yourorg/bago_agentic_data_lab`

**Example tags generated:**
```
ghcr.io/yourorg/bago_agentic_data_lab:main
ghcr.io/yourorg/bago_agentic_data_lab:v1.0.0
ghcr.io/yourorg/bago_agentic_data_lab:sha-abc1234
ghcr.io/yourorg/bago_agentic_data_lab:latest
```

**Manual dispatch:** Go to Actions → Docker Build and Push → Run workflow

---

### ci.yml (Enhanced)

**Key additions:**
- Health check waits before running validation steps
- OpenMetadata: waits up to 2 min for healthy status
- Jaeger: waits up to 1 min for API endpoint
- Prevents race conditions in Docker Compose service startup

**Example:**
```yaml
- name: Wait for Jaeger to be healthy
  run: |
    for i in {1..30}; do
      if curl -s http://localhost:16686/api/services >/dev/null 2>&1; then
        echo "Jaeger is healthy"
        exit 0
      fi
      sleep 2
    done
    exit 1
```

---

### docker-compose-validate.yml

**Validates syntax of all compose files without running them:**
- `docker-compose.ui.yml`
- `infra/openmetadata/docker-compose.yml`
- `infra/observability/docker-compose.yml`

**Triggers:** On changes to compose files or workflow

---

## Dockerfile Optimization

An optimized multi-stage `Dockerfile.ui.optimized` is provided that:

1. **Separates build stages** — Python builder, frontend builder, final slim runtime
2. **Adds healthcheck** — Automatic container health status
3. **Reduces image size** — Uses `--user` and `--no-cache-dir` flags, slim base images
4. **Optimizes layer caching** — Dependencies cached separately from source

**To use:**
```bash
docker build -f Dockerfile.ui.optimized -t bago-portfolio:latest .
```

**Expected size reduction:** ~400MB → ~250MB (typical for Python + Node multi-stage)

---

## Setup Instructions

### 1. Enable GitHub Container Registry (GHCR)

Your workflows already use `secrets.GITHUB_TOKEN` for GHCR authentication. Ensure:
- Repository Settings → Actions → General → Workflow permissions: ✓ "Read and write permissions"

### 2. Optional: Push to Docker Hub

Replace `REGISTRY: ghcr.io` in `docker-build.yml` with:
```yaml
env:
  REGISTRY: docker.io
  IMAGE_NAME: ${{ github.repository_owner }}/bago-portfolio
```

And use Docker Hub secrets:
```yaml
with:
  registry: ${{ env.REGISTRY }}
  username: ${{ secrets.DOCKERHUB_USERNAME }}
  password: ${{ secrets.DOCKERHUB_TOKEN }}
```

### 3. Test Locally

```bash
# Validate Dockerfile
docker build --file Dockerfile.ui.optimized --tag bago-portfolio:test .

# Validate compose files
docker compose -f docker-compose.ui.yml config --quiet

# Test service startup
docker compose -f docker-compose.ui.yml up --detach
curl http://localhost:8080/api/health
docker compose -f docker-compose.ui.yml down
```

---

## Common Patterns

### Build Cache from Registry
```yaml
cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache
cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache,mode=max
```
This stores build layers in a special `buildcache` tag for faster subsequent builds.

### Conditional Steps
```yaml
if: github.event_name != 'pull_request'  # Only on push/dispatch
```

### Multi-stage Builds
```dockerfile
FROM python:3.11-slim as builder
# ... build
FROM python:3.11-slim
COPY --from=builder /app /app
```

---

## Troubleshooting

### Build times out
- Increase `timeout-minutes` in workflow
- Check GitHub Actions limits (6 hour max)
- Verify Docker layer caching is working

### Compose services don't start
- Check health check wait loops
- View service logs: `docker compose logs <service>`
- Verify port availability: `netstat -an | grep 8080`

### GHCR push fails
- Ensure `secrets.GITHUB_TOKEN` is available
- Check Actions → General → Workflow permissions

### Trivy scan fails
- Review results in Security → Code scanning
- High-severity issues should be addressed before merge
- Can suppress false positives with `.trivyignore`

---

## References

- [Docker Buildx GitHub Action](https://github.com/docker/build-push-action)
- [Aqua Trivy Security Scanning](https://aquasecurity.github.io/trivy/)
- [Docker Compose Validation](https://docs.docker.com/compose/compose-file/compose-file-v3/)
- [GitHub Container Registry](https://docs.docker.com/docker-hub/github-actions/)
