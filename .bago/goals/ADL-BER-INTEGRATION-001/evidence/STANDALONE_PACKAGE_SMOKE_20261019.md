# ADL standalone package and BER smoke

## Candidate and artifact

- ADL branch: `codex/adl-ber-integration-20261019`, source HEAD `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` plus the current uncommitted candidate.
- Local image: `bago-portfolio:adl-ber-integration-20261019`.
- Image ID: `sha256:9796d77db7ac8e8e40bf20e00d84661d723228297abd4006789aeab8d92ca02b`; image size reported by Docker: 360,360,692 bytes.
- Bundled BER artifact and lock SHA-256: `da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`.
- Dockerfile now copies the Vite UI-kit entry and package sources required by its multi-entry build, `runtime/ber`, and the bounded BER effect-demo CLI.

## Executed checks

| Action | Command / environment | Result |
|---|---|---|
| Docker packaging contract | `python -m pytest tests/test_docker_workflow.py -q` | PASS, `2 passed`. |
| Build local image | `docker build -f Dockerfile.ui --tag bago-portfolio:adl-ber-integration-20261019 .` | PASS; Vite built both pages and Docker copied source, UI, BER lock/archive and effect-demo CLI. No registry push. |
| Run packaged API and UI | `docker run --rm --name adl-ber-standalone-smoke --publish 127.0.0.1:18872:8080 --env BAGO_API_HOST=0.0.0.0 --env BAGO_RUNTIME_MODE=container bago-portfolio:adl-ber-integration-20261019` | PASS; `/api/health` returned `ok`, `/` returned HTTP 200. Container was stopped and removed after the smoke. |
| Check BER identity and lack of BAGO Full | `docker exec ... python -c ...` inside the running image | PASS; bundled archive SHA matched the lock and `importlib.util.find_spec('bago_core')` returned `None` before BER's private archive extraction. |
| Execute an approved BER effect in the image | `docker exec -i ... python scripts/ber_effect_demo.py --workspace /tmp/ber-demo --effect filesystem.write --path output/ber.txt --content 'container BER smoke'` with `APROBAR filesystem.write` supplied on stdin | PASS; BAGO BER returned receipt `filesystem-write:sha256:8aa7e109d956172571e37c3aae46ea3e8012914c03f0cc7e5e749176d30fac8f`; independent readback matched `container BER smoke`. `filesystem.delete` remained absent from the registered profile. |
| Clean Python runtime check on host | Python 3.11 virtual environment under `%LOCALAPPDATA%\Temp\adl-ber-standalone-e498f1e5597e444992fb81dd3ce3854b`, with only copied ADL `src`, `frontend/dist`, `runtime/ber`, CLI and pinned requirements | PASS; API health `ok`, UI HTTP 200, `bago_core=None`, approved BER write/readback successful. This is a separate isolated venv observation from the Docker image smoke. |

The Docker image is a local build artifact only. It was not pushed, published or
deployed. Live user-provider inference and the Agent Runner websocket were not
part of this package smoke; Agent Runner remains fail-closed pending its own
governed integration and independent verification.

## W17 terminal rebuild after Agent Runner integration

- Candidate: `codex/adl-ber-integration-20261019`, HEAD `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` plus the final uncommitted working tree.
- Rebuilt local image with `docker build -f Dockerfile.ui --tag bago-portfolio:adl-ber-integration-20261019 .`: PASS. Image ID `sha256:b40f0f38d1cc9cca60351f1ffee15a2c123e65efe1ab4244e23b4c861a8b1acf`, size 360,460,424 bytes; frontend production build transformed 129 modules.
- Started the rebuilt image on loopback port 18872 with `BAGO_RUNTIME_MODE=container`: `/api/health` returned `ok`; `/` returned HTTP 200.
- Inside the image, `runtime/ber/bago-embedded-runtime-0.1.0.zip` SHA-256 matched `BER.lock.json` (`da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`); `importlib.util.find_spec('bago_core')` returned `None` before BER private extraction.
- Approved `filesystem.write` in isolated `/tmp/ber-runner-smoke`: BAGO returned receipt `filesystem-write:sha256:34fa249959fb508ef6bb4b7e17d60977ef46897e84e0125d2c4298f2dd41b8af`; independent readback matched `ADL BER Runner terminal smoke`. Container was stopped and removed.
- This is a local build and synthetic isolated smoke only. No push, publish, deploy, live Ollama inference, Agent Runner WebSocket with live services, or `filesystem.delete` occurred.
