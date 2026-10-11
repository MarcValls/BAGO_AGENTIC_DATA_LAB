# W01 - Frozen API and data contract for Agent Evaluation Lab

Candidate: `codex/adl-agent-evaluation-lab-20261010` at base `1e4d9f930da1225ce61ce27def897f76d57a08fc`.

## Bounds
Single-turn, read-only prompt-response evaluation. Real Ollama inference only after explicit Run. No conversation history, tools, workspace access, jobs, arbitrary code, files, external action, or LLM judge. A case makes one provider request. Max 10 cases and one concurrent run per suite. The UI states the request count before run.

## Model and agent identity
- Server reloads agent config from its existing backend store using `agent_id`.
- `model_id` must match an ID returned from configured Ollama model discovery; provider is `ollama-cloud` in this MVP.
- The run stores SHA-256 of canonical JSON of the effective agent config (including its pinned model, if any), selected model, suite version and IDs.
- Never accept system prompt or provider credentials from the browser. Never store/render auth material.

## DTOs
`EvaluationCase`: `{id: string, name: string, prompt: string, must_include: string[], must_not_include: string[]}`.
Limits: name <= 100 chars, prompt 1..4000 chars, each assertion 1..240 chars, <= 8 of each assertion, <=10 cases.
`EvaluationSuite`: `{id, name, agent_id, version, revision, cases, created_at, updated_at}`. IDs prefixed `evalsuite_`; suite versions are immutable. Create uses no ID/version/revision. Update body `{name, agent_id, cases, expected_revision}`; stale revision -> HTTP 409.
`EvaluationCheck`: `{name, passed, detail}`.
`EvaluationCaseResult`: `{case_id, name, status: PASS|FAIL|ERROR, checks, answer_preview, duration_ms, trace: {trace_id?, trace_state, jaeger_trace_id?, jaeger_url?}, error_code?}`. Preview is bounded to 4000 chars and excluded from telemetry.
`EvaluationRun`: `{id, suite_id, suite_version, suite_name, agent_id, agent_name, agent_config_fingerprint, provider_id, model_id, status: PASS|FAIL|ERROR|PARTIAL, total_cases, passed_cases, failed_cases, error_cases, duration_ms, started_at, completed_at, cases}`. No cost or token fields except explicit `not_reported` metadata; never imply zero cost.

## API
- `GET /api/evaluations/suites` -> `{suites: EvaluationSuite[]}`.
- `POST /api/evaluations/suites` -> create from `{name, agent_id, cases}` -> `{suite}`.
- `PUT /api/evaluations/suites/{suite_id}` -> versioned update from `{name, agent_id, cases, expected_revision}` -> `{suite}`.
- `GET /api/evaluations/runs?limit=50` -> `{runs: EvaluationRun[]}`.
- `GET /api/evaluations/runs/{run_id}` -> `{run}`.
- `POST /api/evaluations/suites/{suite_id}/run` from `{revision, model_id}` -> `{run}`. Must preflight suite revision, agent, provider auth/readiness, and model membership before inference.

## Grading and traces
For each completed answer, grade: `response_non_empty`; each required substring occurs case-insensitively; each forbidden substring is absent; `trace_local_saved` is true only if LocalTrace was saved. Overall suite status is PASS if all completed cases pass, FAIL if at least one deterministic check fails and none error, PARTIAL if mixed error and completed cases, ERROR if no case completes. Score, if shown, is only passed assertions / total declared checks and excludes errors; UI must label it “declared checks”, not quality.

Create one LocalTrace per case attempt. Trace attributes include evaluation run/suite/version/case IDs, agent ID/config hash, provider/model, outcome, duration, cost_status=not_reported. Omit prompts and outputs. Save failed provider attempts with safe error code in LocalTrace, without exception text/credentials. Jaeger links appear only after confirmed OTLP export and trace id.

## Persistence
A workspace-isolated SQLite store in local app data, not the repo. Keep append-only suite versions and immutable completed runs with suite snapshot, bounded answer previews, assertion results, trace IDs, and agent fingerprint. Use transaction/revision conflict handling. No run fixtures accepted by the production endpoint.

## Privacy clarification (CR-002)
Credential rejection/redaction is pattern-based and heuristic: it covers labeled credentials, common provider token formats, and high-entropy opaque strings. It cannot reliably detect arbitrary secrets embedded in natural-language text; documentation and UI must instruct users not to include secrets in agent prompts or suite inputs. A test must cover an unlabeled opaque token. This narrows the privacy claim without implying universal secret detection.

## User flow
Expose “Agent Evaluation Lab” in primary Workspace navigation and a chat intent for “open evaluation lab”. The existing portfolio “Evaluation” view remains for governance/demo artifacts. UI has: choose agent/model, suite editor, explicit review/run count, persisted run history, per-case outcome/check/preview, LocalTrace ID and conditional Jaeger link, plus empty/loading/error/unavailable states. Native labeled inputs, buttons and keyboard access required.

## Acceptance
- Tests use temporary DB and provider/trace stubs, and prove redaction, ID consistency, revision conflicts, validation, all overall states and no fallback to fixtures.
- Frontend test covers loading, empty, error, edit/review, explicit run, result/trace, and inaccessible model cases.
- Build/lint where installed; no test/build result inferred from source review.
- One separate live test uses the configured model with one harmless synthetic case and records actual response, model, test identity, LocalTrace ID and provider outcome. Jaeger is separate and may remain NOT_RUN if export is unavailable.
- No commit, push, merge, or publication.
