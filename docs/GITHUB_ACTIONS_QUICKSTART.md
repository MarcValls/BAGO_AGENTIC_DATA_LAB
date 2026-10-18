# GitHub Actions Docker CI/CD — Quick Reference

## ✅ What's Been Set Up

| Item | Status | File | Details |
|------|--------|------|---------|
| Optimized Dockerfile | ✓ | `Dockerfile.ui` | Multi-stage build (361MB), healthcheck included |
| Build workflow | ✓ | `.github/workflows/docker-build.yml` | Auto-push to GHCR on main/tags, Trivy scan |
| Compose validation | ✓ | `.github/workflows/docker-compose-validate.yml` | Validates all yml files on change |
| Enhanced CI | ✓ | `.github/workflows/ci.yml` | Health check waits for Compose services |
| Documentation | ✓ | `docs/` folder | 3 guides + checklist |

---

## 🚀 Getting Started (3 Steps)

### 1. Enable Workflow Permissions
- Go to Repository → Settings → Actions → General
- ✓ "Read and write permissions"
- Save

### 2. Trigger First Build
```bash
git push origin main
```
Or manually: Actions → Docker Build and Push → Run workflow

### 3. Monitor
- Go to Actions tab
- Watch "Docker Build and Push" run
- Should complete in 5–10 minutes
- Verify image in Packages section

---

## 📦 Image Locations

**GHCR (GitHub Container Registry)** — Automatic, no secrets needed
```bash
ghcr.io/yourorg/BAGO_AGENTIC_DATA_LAB:main
ghcr.io/yourorg/BAGO_AGENTIC_DATA_LAB:v1.0.0
ghcr.io/yourorg/BAGO_AGENTIC_DATA_LAB:sha-abc123
```

**Docker Hub** — Optional, requires secrets + config change
```bash
docker.io/yourusername/bago-portfolio:main
```

---

## 📋 Workflows Explained

### docker-build.yml
- **When:** Pushes to main, tags, PRs, manual
- **What:** Builds image, pushes to GHCR (main/tags only), scans with Trivy
- **Output:** Image tags, security report in Security tab
- **Time:** 5–10 min (first), <2 min (cached)

### docker-compose-validate.yml
- **When:** Changes to any `docker-compose*.yml` files
- **What:** Validates YAML syntax
- **Output:** Pass/fail
- **Time:** <30 sec

### ci.yml (Enhanced)
- **When:** Every push/PR
- **What:** Tests, validation, Compose service startup with health checks
- **Output:** Test results, evidence bundle
- **Time:** 30 min (includes all tests)

---

## 🔧 Build Performance

| After | Cache Hit | Time |
|-------|-----------|------|
| **First push** | None | 5–10 min |
| **No code changes** | Full | <2 min |
| **Src change only** | Partial | 1–2 min |
| **Dependency change** | Partial | 2–3 min |

---

## 🛡️ Security

- **Trivy scans** run automatically after each build
- **Results** visible in: Security → Code scanning → Trivy
- **High severity** issues may block merge (depends on policy)
- **Suppress false positives** in `.trivyignore` file

---

## 🧪 Testing Locally

### Build image
```bash
docker build -f Dockerfile.ui -t bago-portfolio:test .
```

### Test with compose
```bash
docker compose -f docker-compose.ui.yml up --detach
curl http://localhost:8080/api/health
docker compose -f docker-compose.ui.yml down
```

### Pull from GHCR
```bash
docker pull ghcr.io/yourorg/bago_agentic_data_lab:main
```

---

## 📖 Documentation Files

- **`docs/github-actions-docker-setup.md`** — Complete workflow guide (what each workflow does, how to extend)
- **`docs/docker-hub-secrets-setup.md`** — Docker Hub configuration (optional dual-registry setup)
- **`docs/docker-actions-verification-checklist.md`** — Step-by-step verification & troubleshooting

---

## ⚠️ Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Build fails with npm error | Frontend build fails | `cd frontend && npm ci && npm run build` locally to debug |
| Image push fails (unauthorized) | Permissions not enabled | Settings → Actions → General → "Read and write permissions" |
| Build takes >10 min on second run | Cache not working | Verify `cache-from`/`cache-to` in workflow match GHCR tag |
| Trivy scan fails | High severity CVE detected | Update dependency or suppress in `.trivyignore` |
| Compose services timeout | Health check endpoint unreachable | Verify service is running: `docker compose logs <service>` |

---

## 🔗 Quick Links

- **Workflows:** `.github/workflows/docker-*.yml`
- **Docker images:** https://github.com/yourorg/BAGO_AGENTIC_DATA_LAB/pkgs/container/bago_agentic_data_lab
- **Build history:** https://github.com/yourorg/BAGO_AGENTIC_DATA_LAB/actions
- **Security scans:** https://github.com/yourorg/BAGO_AGENTIC_DATA_LAB/security/code-scanning

---

## 💡 Next Steps

1. **Verify setup** — Follow checklist in `docs/docker-actions-verification-checklist.md`
2. **Push to trigger build** — `git push origin main`
3. **Monitor first run** — Watch Actions for success
4. **Test image** — Pull and run locally
5. **(Optional) Enable Docker Hub** — Add secrets and update workflow per `docker-hub-secrets-setup.md`
6. **Add deployment** — Use image in staging/production
