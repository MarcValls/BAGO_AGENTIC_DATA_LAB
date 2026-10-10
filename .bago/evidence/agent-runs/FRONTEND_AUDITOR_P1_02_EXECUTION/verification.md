# Independent verification — P1-02 Agent Runner

**Disposition:** `CLOSED` for the reported UI/server contract mismatch in the verified candidate. The Runner now presents execution as unavailable, cannot start a run, and can label a terminal result successful only for an integer `exit_code === 0`.

**Candidate:** `BAGO_AGENTIC_DATA_LAB_chat_control`, branch `codex/agent-chat-control-v1`, HEAD `cf41025e556dbe5850ef3173fa613ac8b6e08887` at verification start. The worktree has unrelated pre-existing modifications; this report binds the relevant files by SHA-256 below. Browser instance record identifies the live UI process as this checkout, at `http://127.0.0.1:8081`.

## Claim → evidence → check → scope

| Claim | Evidence | Check performed | Scope / conclusion |
|---|---|---|---|
| Original P1-02 described an exposed Run affordance despite no server execution capability. | `.bago/CRIT-BAGO-ADL-FRONTEND-20261009-01.md`, P1-02 (lines 31–36); W01 handoff `.codex-team/handoffs/W01.json` | Independently reread source report and validated W01 handoff with `teamctl.py --root <evidence-folder> verify` (`PASS verify`). | Confirms the finding and W01 evidence as the input to this verification. |
| The authoritative server remains fail-closed and starts no job. | `src/api/server.py:968–985`: `/ws/agents/run` emits `type=error`, `code=execution_unavailable`, says no job was started/recorded, then closes with code 1008. | Read the current handler in this candidate; did not call the WebSocket endpoint. | Source-level server behavior verified. No runtime execution attempt was made. |
| The UI reports unavailable and disables the Run action. | `frontend/src/components/AgentRunner.tsx:25,58–61,214–220`; rendered page shows the status and disabled “Run unavailable” button. | Headed Playwright opened the live app, navigated to Agent Runner, captured an accessibility snapshot, rebuilt, reloaded, revisited Runner and captured the final rendered state. | Rendered behavior verified for the UI served from this checkout. The button was disabled; it was not clicked. |
| The code cannot represent an absent, non-integer, or nonzero exit code as success. | `AgentRunner.tsx:85–100`: `Number.isInteger` normalizes invalid values to `null`, and both status and success notification require `exitCode === 0`. | Independent source inspection; frontend build passed. | Source logic verified; these terminal branches were not dynamically exercised because no executor exists and Run is disabled. |
| The browser evidence matches the observed state. | `output/playwright/agent-runner-disabled-p1-02-20261009.png` (SHA-256 `6770b64c65f90c1c92fa6615de825a3985c545c899d9d5b2ed09c1bf700cb478`); `.playwright-cli/page-2026-10-09T17-02-52-087Z.yml` | Screenshot was visually inspected; snapshot names the Agent Runner region, unavailable status, one agent, and disabled Run button. | UI evidence for this browser session and timestamp, not a production deployment claim. |

## Final source fingerprints

- `frontend/src/components/AgentRunner.tsx`: `defb5670ba4fe415de6e65ed7c621f4f7c7806df988e91fc73ddd85f11a22315`
- `frontend/src/components/AgentRunner.css`: `c81c6ea2d7c86e3c438807b4dbd2536d09753b43ceae6ad65ac72b1271d5ea89`
- `src/api/server.py`: `e1450ab9d4510ce165063437d58c679529bb45673be59ff7b68e65b398a1a56c`

These Runner hashes match W01's recorded hashes. The build ran after the hash check and the source hashes were re-read afterward; the browser was reloaded and revisited after the build.

## Verification commands

- `git diff --check` — PASS; no whitespace errors. Git emitted only existing LF/CRLF normalization notices.
- `npm run build` in `frontend` — PASS (`tsc -b && vite build`; Vite 4.5.14; 126 modules transformed).
- Headed Playwright on `http://127.0.0.1:8081` — PASS for visible unavailable state and disabled Run control. Evidence above.
- `python .codex-team-kit/scripts/teamctl.py --root <evidence-folder> verify` before W02 handoff — PASS for W01 dependency handoff.

## Attribution and evidence limits

W01 was performed by the Codex engineering subagent recorded as `/root/p1_02_implementer`; this report is the independent Codex verification pass. **This does not establish that the Ollama Frontend Auditor inspected source files, used tools, ran, or changed code.** No Ollama inference or Jaeger span is evidence for this P1-02 repair. No agent execution, WebSocket invocation, or button click was attempted.

The browser console also recorded a 404 for `/api/artifacts` while loading the default Chat view. It did not block navigation or rendering of Agent Runner; it is outside P1-02 and is not adjudicated here.

## Closure decision

`P1-02 = CLOSED` against its stated acceptance: the user-facing Runner no longer promises an available execution action while the server has no governed executor, and terminal success is gated on exit code zero. **Execution capability itself remains unavailable.** A future implementation of a governed executor must re-open this boundary for end-to-end success, failure, authorization, and receipt verification; this closure does not claim those flows exist or work.
