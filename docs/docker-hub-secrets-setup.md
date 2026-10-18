# Docker Hub Secrets Configuration

## Option 1: GitHub Container Registry (GHCR) — Recommended for GitHub-hosted projects

**Status:** Already configured in `docker-build.yml`

GHCR automatically uses `secrets.GITHUB_TOKEN`, so no additional setup needed.

**Verify:**
1. Go to your repository → **Settings** → **Actions** → **General**
2. Under "Workflow permissions", ensure ✓ **"Read and write permissions"**
3. Click **Save**

**Images will be available at:**
```
ghcr.io/yourorg/bago_agentic_data_lab:latest
ghcr.io/yourorg/bago_agentic_data_lab:v1.0.0
```

---

## Option 2: Docker Hub — Additional setup required

### Step 1: Create Docker Hub Access Token

1. Go to [Docker Hub](https://hub.docker.com/)
2. Sign in with your Docker Hub account
3. Click **Account Settings** → **Security** → **New Access Token**
4. **Access Token Description:** `GitHub Actions BAGO`
5. **Permissions:** Read & Write
6. Click **Generate**
7. Copy the token (you won't see it again)

### Step 2: Add GitHub Secrets

1. Go to your GitHub repository
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Create two secrets:

| Name | Value |
|------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Token from Step 1 |

### Step 3: Update docker-build.yml

Replace the `env` section at the top of `.github/workflows/docker-build.yml`:

```yaml
env:
  REGISTRY: docker.io
  IMAGE_NAME: ${{ github.repository_owner }}/bago-portfolio
```

Replace the `Log in to Container Registry` step:

```yaml
      - name: Log in to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
```

### Step 4: Test the configuration

Push a commit or manually trigger the workflow:
1. Go to **Actions** → **Docker Build and Push**
2. Click **Run workflow** → **Run workflow**
3. Wait for completion
4. Verify image on Docker Hub: `docker.io/yourusername/bago-portfolio`

---

## Option 3: Dual Push (Both GHCR + Docker Hub)

If you want to push to both registries simultaneously:

```yaml
env:
  GHCR_REGISTRY: ghcr.io
  DOCKERHUB_REGISTRY: docker.io
  GHCR_IMAGE: ${{ github.repository }}
  DOCKERHUB_IMAGE: ${{ github.repository_owner }}/bago-portfolio

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.GHCR_REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Log in to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.DOCKERHUB_REGISTRY }}
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract GHCR metadata
        id: ghcr_meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.GHCR_REGISTRY }}/${{ env.GHCR_IMAGE }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha,prefix={{branch}}-

      - name: Extract Docker Hub metadata
        id: dockerhub_meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.DOCKERHUB_REGISTRY }}/${{ env.DOCKERHUB_IMAGE }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha,prefix={{branch}}-

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.ui
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ${{ steps.ghcr_meta.outputs.tags }}
            ${{ steps.dockerhub_meta.outputs.tags }}
          labels: |
            ${{ steps.ghcr_meta.outputs.labels }}
            ${{ steps.dockerhub_meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.GHCR_REGISTRY }}/${{ env.GHCR_IMAGE }}:buildcache
          cache-to: type=registry,ref=${{ env.GHCR_REGISTRY }}/${{ env.GHCR_IMAGE }}:buildcache,mode=max
```

---

## Monitoring Your First Build

### Watch the workflow run:

1. Push a commit or tag to main
2. Go to **Actions** tab
3. Click **Docker Build and Push**
4. Monitor these steps:
   - ✓ **Set up Docker Buildx** — Usually instant
   - ✓ **Extract metadata** — Generates tags (should show `main`, `sha-abc...`)
   - ⏳ **Build and push** — First build: 3–5 min (no cache); subsequent: <1 min
   - ✓ **Run Trivy scan** — Security scan (30s–2 min)

### Expected output for a successful build:

```
docker/build-push-action: Building ...
docker/build-push-action: Pushing image...
docker/build-push-action: [0] => => pushing manifest for ghcr.io/yourorg/bago_agentic_data_lab:main
docker/build-push-action: [0] => => pushing manifest for ghcr.io/yourorg/bago_agentic_data_lab:sha-abc1234
```

### Verify the image:

**GHCR (GitHub):**
```bash
docker pull ghcr.io/yourorg/bago_agentic_data_lab:main
docker run -p 8080:8080 ghcr.io/yourorg/bago_agentic_data_lab:main
```

**Docker Hub (if configured):**
```bash
docker pull yourusername/bago-portfolio:main
docker run -p 8080:8080 yourusername/bago-portfolio:main
```

### Check build performance:

In the workflow run, look for the build summary:
```
=> [builder 1/2] FROM python:3.11-slim
=> [builder 2/2] RUN pip install --user ...  (cached)
=> [frontend-builder 2/2] RUN npm ci && npm run build
=> [stage-3 2/3] COPY --from=builder ...  (cached)
```

`(cached)` entries = layers reused from previous builds. On the first build, expect everything to build. On subsequent runs with no dependency changes, you should see most layers cached.

---

## Troubleshooting

### Build fails with authentication error
- Verify `secrets.GITHUB_TOKEN` has read/write permissions
- For Docker Hub: ensure token is copied completely (no spaces)
- Go to **Settings** → **Secrets** to verify secret values are set

### Image not found after push
- Check workflow run completed successfully
- Pull directly: `docker pull ghcr.io/yourorg/bago_agentic_data_lab:main`
- Verify package visibility: go to **Packages** on your profile

### Build takes >5 minutes
- First build always slower (no cache)
- Check if frontend build is failing silently (npm install issues)
- Review logs for `npm ci` or `pip install` errors

### Trivy scan blocks merge
- Review Security → Code scanning → Trivy results
- Filter by severity, suppress false positives in `.trivyignore`
- High-severity items should be investigated before merge

---

## Next Steps

1. Verify workflow permissions: Repository → Settings → Actions → General
2. (Optional) Add Docker Hub secrets if using Option 2 or 3
3. Push a commit to trigger the first build
4. Monitor the Actions run and verify image appears in your registry
5. Test pulling and running the image locally
