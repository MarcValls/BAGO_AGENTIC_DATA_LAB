# Live Agent Runner and refreshed standalone package evidence

Date: 2026-10-19 20:04 UTC

## Candidate binding

- ADL branch/HEAD: `codex/adl-ber-integration-20261019` / `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` plus the current uncommitted candidate.
- Agent Runner source SHA-256: `61a4196324403dd667b5245eac968943498f078c3f52374c59b2f51b02181a87`.
- ADL API source SHA-256: `1b030ebd525aad7fc9ffd98b62e130ab4cc4a74497381f2625d3f82ab6b92195`.
- Pinned BER archive SHA-256: `da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22`; the packaged lock contains the same digest.

## Live local Ollama through the candidate Agent Runner

The candidate API source was launched on loopback port `18873` from this
worktree. Its test-only launch configuration selected `local_cli` and
`llama3.2:3b` in process memory; it did not edit the saved provider config or
read/use the configured Ollama Cloud credential. The real local Ollama service
reported `llama3.2:3b` in `/api/tags`. The app process reported health `ok`,
provider `configured_unverified`, runtime `host`, and model
`llama3.2:3b`.

An ephemeral saved profile (`agent_c5839466a96644ff`, profile SHA-256
`06d129e2bdf0eb3c88949dd0913ae47095a4ca9634abe79d05404e4816b866bb`) had no
tools and pinned that local model. Its workspace was a disposable Git
repository with HEAD `0abe0016c5ca84aa644a2a098f1fc2d2c0b6a252`. A WebSocket
start on `/ws/agents/run` returned:

```json
{"type":"task_result","run_id":"run_ac24a18d50d047b0a7e6b0dd9cf82e2d","task_status":"answered","effect_status":"not_started","answer":"BER_LIVE_OK"}
```

This exercises the candidate Runner, starts the pinned BER client before the
provider call, receives a real local Ollama response, and closes without an
effect or receipt. A first attempt against an empty, unborn Git repository
failed closed with `runtime_unavailable`; after committing the synthetic seed,
the same request completed. The temporary API process, agent profile and
workspace were then removed. The host virtual environment and final container
both reported `bago_core_available=false`.

**Scope limit:** this is a live no-effect Agent Runner task. A live model
proposal followed by a governed mutating Runner approval/execution was not
performed; W16 adversarial proposal, approval and receipt checks used
deterministic fakes. The standalone BER effect path below used its explicit
synthetic test confirmation.

## Rebuilt standalone image after the provider-page correction

| Check | Action and evidence | Result |
|---|---|---|
| Build candidate image | `docker build -f Dockerfile.ui --tag bago-portfolio:adl-ber-integration-20261019-final .` | PASS; local image ID `sha256:ff799aad7b0f2ed3fe0c3869491bf2cb0c72a10bb127a8bd799b83eda133c5ff`, size 360,461,015 bytes; Docker rebuilt Vite from the corrected frontend, 129 modules. |
| API/UI smoke | Started exact image on loopback `127.0.0.1:18874` | `/api/health` returned `ok`; `/` returned HTTP 200. |
| Runtime identity / BAGO Full absence | Inspected the running image | BER archive SHA matched `BER.lock.json`; `importlib.util.find_spec('bago_core')` returned `None`. |
| Approved BER write | `scripts/ber_effect_demo.py` in the container, isolated workspace `/tmp/ber-final-runner-smoke`, typed `filesystem.write` to `output/ber.txt` | PASS; BAGO returned receipt `filesystem-write:sha256:e22d46773d40feb2d1798edb811045bf2bdbcb38c12e5e1c85d22d5035129dab`. Independent readback returned exactly `BER_FINAL_STANDALONE`. |
| Cleanup | Stopped the named smoke container and candidate host API; removed only the unique temporary host fixture | PASS; ports 18873/18874 are free, container and temporary workspace are absent. The local image tag remains available for review. |

No image push, publication, or deployment occurred. `filesystem.delete` was
not invoked and remains unavailable in the BER profile.
