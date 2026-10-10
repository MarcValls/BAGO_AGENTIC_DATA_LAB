# Agent Evaluation Lab: backend contract

The Evaluation Lab stores workspace-isolated, versioned suites and immutable run snapshots in SQLite under the user's local application data. `BAGO_AGENT_EVALUATION_DB_PATH` can point to a temporary database for tests. Trace JSON is stored beside that database under `traces/`, outside the repository workspace.

## API

- `GET /api/evaluations/suites` lists current suite versions.
- `POST /api/evaluations/suites` creates `{name, agent_id, cases}`.
- `PUT /api/evaluations/suites/{suite_id}` creates a new immutable version from `{name, agent_id, cases, expected_revision}`; stale revisions return `409`.
- `GET /api/evaluations/runs?limit=50` and `GET /api/evaluations/runs/{run_id}` read saved run history.
- `POST /api/evaluations/suites/{suite_id}/run` accepts `{revision, model_id}`. It checks suite revision, agent record, configured provider state, and exact model membership before the first inference. Each case makes exactly one real provider request. Provider errors remain `ERROR`; the endpoint never substitutes a fixture.

Each case is `{id?, name, prompt, must_include?, must_not_include?}`. Limits are 10 cases, 4,000 prompt characters, eight assertions per list and 240 characters per assertion. Grading checks a non-empty answer, required case-insensitive substrings, forbidden substrings, and whether its local trace was saved. The score describes only declared checks; it is not a model-quality judgment.

## Safety and evidence

The API resolves the system prompt from the persisted agent. It accepts neither a system prompt nor credentials from the browser. Recognized credential formats, common provider-token prefixes and high-entropy opaque strings in saved agent prompts or suite inputs are rejected; matching patterns echoed by an answer are redacted from its bounded 4,000-character preview. This is heuristic detection: arbitrary secrets embedded in natural-language text cannot be identified reliably, so agent prompts and evaluation inputs must not contain secrets. Long hexadecimal values are conservatively treated as credential-like, which can reject legitimate hashes or digests. Previews are excluded from traces. LocalTrace events contain run/suite/version/case/agent/model identity, outcome, duration and `cost_status=not_reported`; prompts, outputs, exception text and matched credential patterns are omitted. Jaeger IDs/URLs are returned only after confirmed OTLP export and a received trace ID. No usage or cost is inferred as zero.

`PASS` means all declared checks passed. `FAIL` means at least one completed answer failed a declared check. `PARTIAL` means a run contains both provider errors and completed cases. `ERROR` means no case completed. Deterministic string checks do not establish correctness, safety or general answer quality.
