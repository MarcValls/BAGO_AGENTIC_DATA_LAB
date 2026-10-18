# GitHub Actions Docker CI/CD Setup Verification Checklist

## Pre-Launch Verification

- [x] **Dockerfile.ui replaced** with optimized multi-stage build
  - Status: ✓ Image builds successfully (361MB)
  - Stages: Python builder → Node frontend builder → Final slim runtime
  - Layer caching: Enabled via `--user` flags and separated dependencies

- [x] **docker-compose.ui.yml validated**
  - Status: ✓ Valid configuration (run `docker compose -f docker-compose.ui.yml config --quiet`)

- [x] **GitHub workflows created**
  - `.github/workflows/docker-build.yml` — Build, push, scan
  - `.github/workflows/docker-compose-validate.yml` — Syntax validation
  - `.github/workflows/ci.yml` — Enhanced with health check waits

- [x] **Documentation written**
  - `docs/github-actions-docker-setup.md` — Complete workflow guide
  - `docs/docker-hub-secrets-setup.md` — Registry configuration options

---

## Repository Configuration (Required Before First Run)

### Step 1: Verify GitHub Actions Permissions

1. Go to your repository → **Settings**
2. Navigate to **Actions** → **General**
3. Under "Workflow permissions", ensure:
   - ✓ **"Read and write permissions"** (REQUIRED for GHCR pushes)
   - ✓ **"Allow GitHub Actions to create and approve pull requests"** (optional but recommended)
4. Click **Save**

**Status:** ⏳ Needs manual verification

### Step 2: (Optional) Add Docker Hub Secrets

Only if you want to push to Docker Hub in addition to GHCR:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:
   - Name: `DOCKERHUB_USERNAME` | Value: Your Docker Hub username
   - Name: `DOCKERHUB_TOKEN` | Value: Your Docker Hub access token
3. Update `.github/workflows/docker-build.yml` to use Docker Hub (see `docs/docker-hub-secrets-setup.md` Option 2)

**Status:** ⏳ Optional — only if you want Docker Hub push

---

## First Run Checklist

### Trigger the Build

Choose one:

**Option A: Push a commit**
```bash
git add Dockerfile.ui .github/workflows/
git commit -m "chore: replace Dockerfile.ui with optimized multi-stage build and add GitHub Actions workflows"
git push origin main
```

**Option B: Manual dispatch** (test without committing)
1. Go to **Actions** → **Docker Build and Push**
2. Click **Run workflow** → **Run workflow**
3. Wait for completion

### Monitor the Build (5–10 minutes)

1. Go to **Actions** tab → **Docker Build and Push** run
2. Watch for these stages:

| Stage | Expected Duration | What It Does |
|-------|-------------------|--------------|
| Checkout | <10s | Clone repo |
| Set up Docker Buildx | <10s | Prepare builder |
| Extract metadata | <5s | Generate tags (should show `main`, `sha-xxxxx`) |
| Build and push | 3–5 min (first run) | Multi-stage build, push to GHCR |
| Run Trivy scan | 1–2 min | Security vulnerability scan |

3. Look for these log lines:
   ```
   => [builder 1/3] FROM python:3.11-slim
   => [builder 2/3] COPY requirements.txt
   => [builder 3/3] RUN pip install --user ...
   => [frontend-builder 1/3] FROM node:22-alpine
   => [frontend-builder 2/3] COPY frontend
   => [frontend-builder 3/3] RUN npm ci && npm run build
   => [stage-2 1/4] FROM python:3.11-slim
   => [stage-2 2/4] COPY --from=builder /root/.local
   => [stage-2 3/4] COPY --from=frontend-builder
   => [stage-2 4/4] COPY src
   => exporting to image
   ```

### Verify Image Built Successfully

**In GitHub Actions logs:**
```
docker/build-push-action: [1] => => pushing manifest for ghcr.io/yourorg/bago_agentic_data_lab:main sha256:abc123def456
docker/build-push-action: [1] => => pushing manifest for ghcr.io/yourorg/bago_agentic_data_lab:sha-abc1234
```

**In GitHub Packages:**
1. Go to your repository → **Packages** section (right sidebar)
2. Click the `bago_agentic_data_lab` package
3. Should see tags: `main`, `sha-xxxxx`

### Verify Security Scan

1. Go to **Security** → **Code scanning**
2. Click **Trivy** results
3. Review any findings (typically low/medium severity warnings)
4. If critical issues appear, they will also block the workflow

### Test Pulling the Image

```bash
# Authenticate to GHCR
echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin

# Pull the newly pushed image
docker pull ghcr.io/yourorg/bago_agentic_data_lab:main

# Run it
docker run -p 8080:8080 ghcr.io/yourorg/bago_agentic_data_lab:main

# Test the health check
curl http://localhost:8080/api/health

# Stop
docker stop <container_id>
```

---

## Subsequent Build Performance

### Expected Build Times

| Scenario | Time | Details |
|----------|------|---------|
| **First build** | 5–10 min | No cache, all layers built |
| **No changes** | <2 min | All layers cached from registry |
| **Dependency changes** | 2–3 min | Invalidates pip/npm cache, layers below reused |
| **Source code changes** | 1–2 min | COPY layers rebuild, everything else cached |

### Verify Layer Caching Works

After the first successful build, make a small change and push:

```bash
# Change a comment in a source file
echo "# test" >> src/api/server.py
git add src/
git commit -m "test: verify cache hits"
git push origin main
```

In the second build logs, you should see:
```
=> [builder 2/3] COPY requirements.txt  (cached)
=> [builder 3/3] RUN pip install ...    (cached)
=> [frontend-builder 2/3] ...           (cached)
=> [frontend-builder 3/3] ...           (cached)
=> [stage-2 2/4] COPY --from=builder    (cached)
```

The build time should drop to ~1 min.

---

## Docker Compose CI Steps

The enhanced `ci.yml` now validates Compose services with health checks:

### OpenMetadata Validation

1. Starts container: `docker compose ... up -d`
2. Waits up to 2 minutes for healthy status
3. Runs validation script
4. Stops and removes (even if failed)

**If this fails:** Check `infra/openmetadata/docker-compose.yml` healthcheck definition

### Jaeger Validation

1. Starts container: `docker compose ... up -d`
2. Waits up to 1 minute for API endpoint (`http://localhost:16686/api/services`)
3. Runs validation script
4. Stops and removes

**If this fails:** Ensure Jaeger OTLP collector is enabled in `infra/observability/docker-compose.yml`

---

## Troubleshooting

### Build fails: "npm ci failed"
- **Cause:** Frontend dependencies not installing
- **Fix:** Check `frontend/package*.json` files exist and are valid
- **Workaround:** Try locally: `cd frontend && npm ci && npm run build`

### Build fails: "python pip install failed"
- **Cause:** Dependency conflict or version mismatch
- **Fix:** Verify `requirements.txt` versions are compatible
- **Workaround:** Try locally: `pip install -r requirements.txt fastapi uvicorn`

### Image push fails: "denied: unauthorized"
- **Cause:** Workflow permissions not configured
- **Fix:** Go to **Settings** → **Actions** → **General** → enable "Read and write permissions"

### Trivy scan blocks PR
- **Cause:** Security vulnerability detected
- **Fix:** Review in **Security** → **Code scanning**, update dependency, or suppress in `.trivyignore`

### First build takes >10 minutes
- **Cause:** Large dependencies, slow network, or resource contention
- **Fix:** GitHub Actions usually have sufficient resources; check runner logs for bottlenecks

### Second build still takes 5+ minutes (cache not working)
- **Cause:** Cache not enabled or stored in wrong location
- **Fix:** Verify `cache-from` and `cache-to` directives in `docker-build.yml` reference the correct GHCR tag

---

## Next: CI Integration

After the first build succeeds:

1. **Tag for release:** `git tag -a v1.0.0 -m "Release 1.0.0"` → pushes image with semver tag
2. **Add more tests:** Extend CI to run container tests (`docker run --rm ...`)
3. **Deploy:** Use the image in your deployment pipeline (K8s, Docker Swarm, Cloud Run, etc.)
4. **Monitor:** Set up alerts on failed builds in GitHub Actions

---

## References

- [Docker Build and Push Action](https://github.com/docker/build-push-action)
- [Docker Metadata Action](https://github.com/docker/metadata-action)
- [Trivy Vulnerability Scanner](https://aquasecurity.github.io/trivy/)
- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Compose File Reference](https://docs.docker.com/compose/compose-file/)

---

## Quick Links

- **GitHub Actions Status:** https://github.com/yourorg/BAGO_AGENTIC_DATA_LAB/actions
- **Packages (Published Images):** https://github.com/yourorg/BAGO_AGENTIC_DATA_LAB/pkgs/container/bago_agentic_data_lab
- **Workflow Files:** `.github/workflows/docker-*.yml`
- **Documentation:** `docs/github-actions-docker-setup.md` + `docs/docker-hub-secrets-setup.md`
