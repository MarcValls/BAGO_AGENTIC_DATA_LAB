# ADL real agent turn: browser, persistence and Jaeger

## Scope

One bounded read-only turn was run in the Agentic Data Lab app at `http://127.0.0.1:8084/`. The user explicitly enabled read access for that message. The agent was allowed to use the app's single bounded `read_workspace_file` tool; it had no registered tools, file-write capability, command execution, or job execution.

The challenge file was `.goals/ADL-OLLAMA-SPIRAL-001/evidence/CHAT_READ_TEST.txt`. Its expected marker was `COBALTO-47-FARO`. The marker file is test input; the model response was generated live by Ollama Cloud.

## Evidence comparison

| Claim | ADL browser/API | Persisted LocalTrace and conversation | Jaeger projection | What the evidence establishes |
|---|---|---|---|---|
| A real provider response occurred | `POST /api/agents/agent_d3e63db8b4704080b924a05fb1ab71fc/chat` returned HTTP 200 in 2,610 ms. Response says `source=ollama`; selected model badge showed `gemma4:31b`. | `agent.chat` is `COMPLETED`; attributes say `provider_id=ollama-cloud`, `model_id=gemma4:31b`, `outcome=response_received`. | One `agent.chat` span, service `bago-agentic-data-lab`, status `OK`; tags carry the same provider and model. | An actual Ollama Cloud-backed agent request completed. This is not a fixture response. |
| The agent read the requested file | UI shows the response and `Project files read` receipt for the exact path, lines 1–3. The request body has `allow_workspace_read=true`; response `sources` contains the same path/range. | Event records `workspace_read_count=1` and the source path/range. Stored assistant message references contain the source receipt. | Span tags preserve `workspace_read_sources` for lines 1–3. | The app's read-only tool returned the exact file range to the live model. |
| The answer came from the file | Assistant response returns `COBALTO-47-FARO` and cites line 2. | The stored assistant message contains the marker and line citation. | Jaeger does not store the response text; its tags identify the source and model only. | The browser and conversation store prove the answer text. Jaeger corroborates execution metadata, not answer content. |
| The conversation persisted | Browser displayed the completed response. | Conversation `conv_144a84b37b604678a4fc6c60af55ef85` has two complete messages at revision 2. API and SQLite readback after an app restart returned both messages and the trace/source references. | The span's agent id and local trace id correlate to the conversation's assistant-message reference. | The user and assistant turn survived an app restart in the per-user conversation database. |
| The trace is visible in Jaeger | At request time the app response/header reported `trace_state=local_only` and local trace id `trace-ce1f60b61fc34e13`. | The canonical LocalTrace file is `.bago/traces/agent-chat/trace-ce1f60b61fc34e13.json`; it remains the source of truth. | After the turn, that LocalTrace was explicitly projected to the local OTLP endpoint. Jaeger API and UI show trace id `75ee12eb3a775282a950d4c603c651c4`, one `agent.chat` span, 2,578,127 μs, and the matching `bago.trace_id` attribute. | Jaeger has a verifiable projection of the same completed event. It was exported after the chat; the app did not automatically attach a Jaeger link to that response. |

## Model identity

The original configured string was `gemma4:31b-cloud`. The authenticated Ollama Cloud catalog did not list that string; it listed `gemma4:31b` with source `ollama_cloud_api`. Provider Settings saved and verified the listed ID, and the agent draft was reviewed before saving. The real turn used exactly `gemma4:31b`. This report does not assert that the two strings are interchangeable aliases.

## Timing and cost

The browser request duration was 2,610 ms. The LocalTrace event duration was 2,578 ms, and Jaeger shows 2,578,127 μs for the projected span. The small difference is consistent with browser/API overhead. Ollama did not report a model cost, so cost remains unknown.

## Artifacts

- ADL response screenshot: `output/playwright/ollama-spiral-real-agent-turn-20261009.png`
- Jaeger UI screenshot: `output/playwright/jaeger-ollama-spiral-trace-20261009.png`
- LocalTrace: `.bago/traces/agent-chat/trace-ce1f60b61fc34e13.json`
- Conversation/trace verification receipt: `.goals/ADL-OLLAMA-SPIRAL-001/evidence/W04_CONVERSATION_TRACE_VERIFICATION.json`
- Browser response receipt: `.goals/ADL-OLLAMA-SPIRAL-001/evidence/W03_REAL_AGENT_TURN.json`

## Evidence boundary

The live turn proves read-only access to this one bounded text file and a response from the selected provider/model. It does not prove the agent audited source code, changed files, executed jobs, or validated the earlier P1-02 finding. The Jaeger span is an observability projection, not execution authority. The app's response itself initially had only local trace metadata; the Jaeger projection was a separate post-run action.
