# W02 — Evaluation Lab: UX and portfolio map

**Mission:** `ADL_AGENT_EVALUATION_LAB_SPIRAL_001`  
**Candidate:** `codex/adl-agent-evaluation-lab-20261010`  
**Bound HEAD:** `1e4d9f930da1225ce61ce27def897f76d57a08fc`  
**Method:** read-only source and documentation inspection. No product files edited; no tests or live provider calls run.

## Finding

The app already has the right adjacent building blocks for an Agent Evaluation Lab: a persistent chat library, selectable agents, a provider/model configuration surface, a portfolio Evaluation page, LocalTrace identity in chat messages, and a detailed Decision Inspector trace timeline. The present Evaluation page is a static view over the demo artifact bundle and deterministic governance checks. It is not an interactive, repeatable evaluation of an existing chat agent against a case suite, and its “PASS” interpretation concerns governance/evidence completeness rather than answer quality.

This distinction is the main UX risk: reusing the name and existing PASS card without explicitly naming the evaluated suite/case, agent, effective model, assertions, and run identity could make a governance check look like model-quality evaluation.

## Existing entry points and navigation

| Surface | Current behavior in source | UX implication |
|---|---|---|
| App shell | Chat is the initial view. Chat, Capabilities, Decision Inspector, Agent Builder, and Agent Runner are in the primary workspace navigation. Control, Job History, Summary, Retrieval & Ontology, Authorization, Trace, and Evaluation sit inside the collapsed “Other portfolio views” disclosure. Provider Settings is also inside that disclosure and linked from the header. (`frontend/src/App.tsx:26-43,49,86-98`) | Evaluation takes an extra disclosure step from the landing view. Add a direct, clearly named Evaluation Lab entry while retaining the existing artifact Evaluation as a distinct view/section, or expose the lab as the primary evaluation destination. Avoid making Chat responsible for silently starting runs. |
| Chat and conversation library | Chat supports App Assistant or a selected agent; it has Recent/Archived/Trash conversations and New. Messages can show source file ranges and LocalTrace/Jaeger metadata. (`frontend/src/components/AgentChat.tsx:21-23,461-488`) | A user can preserve a natural-language planning conversation and inspect existing trace links. Use chat to explain or prepare an evaluation, then route to an explicit review/run screen. Do not place a run action behind an ambiguous chat intent. |
| Existing Evaluation | `App` fetches `/api/artifacts` and passes `artifacts.evaluation` to the page. The page renders status, score, cost, governance checks, evidence references and a fixed “What Was Validated” list. (`frontend/src/App.tsx:52-65,77,104-115`; `frontend/src/components/Evaluation.tsx:15-43,46-80,83-102`) | This is a portfolio artifact reader, not a suite editor, agent/model selector, run history, or per-case result screen. Preserve its governance meaning and label it accordingly if adjacent to the new lab. |
| Existing trace inspection | Decision Inspector displays the LocalTrace and run IDs and currently states that Jaeger correlation is unavailable. (`frontend/src/features/decision-inspector/trace/TraceTimeline.tsx:45-55`) | A future evaluation result should link to its source trace only when the run actually supplies that identity. Treat absent trace/Jaeger correlation as explicit “unavailable”; do not synthesize a Jaeger link. |

## Smallest coherent user flow

1. Open **Evaluation Lab** from the workspace navigation (or one clearly named link from Chat). Show a one-line explanation: “Run saved cases against an existing agent and inspect deterministic checks and traces.”
2. Select an existing agent and show the **effective provider/model** the server will use. Keep discovery/listing distinct from verified live inference; block Run when either identity is unavailable.
3. Select or create a small named, versioned suite. Each case shows its input and explicit deterministic assertions (for example required/forbidden text). Explain that these assertions are checks, not an LLM judge or a complete quality score.
4. Review the suite, selected agent/model, and expected provider call count; then press a clearly labeled **Run evaluation** control. This explicit action is the boundary between editing inputs and making a real provider request.
5. Show one compact run summary followed by case rows: pass/fail/error, assertion detail, elapsed time, and trace status/ID. Offer a trace drill-down without losing suite/run context. Show provider unavailable, missing model, failed call, and missing trace as distinct states; never convert them into a passing result.

This flow keeps setup, approval to consume provider inference, outcomes, and trace evidence visible without adding a second chat surface. It stays read-only with respect to workspace files and job dispatch.

## Low-cognitive-load recommendations and acceptance measures

- Keep the main path to **five explicit steps or fewer** from Chat to first reviewable run: open lab, choose agent/model, choose suite, review, run. Measure with a scripted first-run journey and record any required detours.
- At the top of every run result, display **suite name + version, agent ID/name, effective provider/model, run status, and run ID** in one compact identity block. A reviewer should identify what ran without opening a detail panel.
- Keep case outcome and failed assertion visible in the first screenful for a small starter suite; provide trace details on demand. Measure by a usability check where a reviewer identifies the failed case and opens its trace without searching unrelated portfolio pages.
- Make “Run evaluation” the only control that starts provider inference. Before it, state the suite size/call count; after it, retain the submitted suite version and immutable run record so edits cannot rewrite prior results.
- Use explicit text labels as well as color for `PASS`, `FAIL`, `ERROR`, `NOT RUN`, and `TRACE UNAVAILABLE`; preserve keyboard focus and native button/form labels. Verify keyboard-only completion and screen-reader names in a later UI validation pass.
- Add a small empty state with one action (“Create evaluation suite”) and one truthful prerequisite (“Choose an existing agent with a confirmed model”). Avoid placeholder sample results that could be mistaken for live runs.

## Portfolio and market-facing evidence gap

`JOB_SKILL_MATRIX.md:142-167` marks Evaluation “Muy Alta” and distinguishes current “Local governance evals” from the target “Framework”; it also identifies live model evaluation as evidence still needed for Bedrock and Bedrock Knowledge Bases (`:161-162`). This supports the portfolio direction as an internal prioritization signal. In the inspected matrix and adjacent portfolio documents, the demand labels are not accompanied by a market report, dated source, job-posting sample, or methodology. Therefore this UX map does **not** validate an external market-demand claim.

The existing observability documentation is explicit that `LocalTraceEvaluator` checks workflow/evidence structure and **does not judge semantic answer quality**; the reproducible L12 path uses an injected provider fixture (`docs/observability_evals.md:19-39,41-50`). Present that as valuable governance/observability evidence, while positioning the new capability as a complementary, real-provider, deterministic case-evaluation demonstration. A genuine provider-backed run and its linked run/model/trace evidence would be stronger portfolio proof than a static governance score; it still would not constitute a broad benchmark or prove general model quality.

## Evidence boundary

- Source-level findings are bound to the candidate HEAD above; this assignment did not run the UI, API, test suite, or Ollama.
- No market source was present in the inspected `JOB_SKILL_MATRIX.md`, `docs/portfolio_ui.md`, `docs/observability_evals.md`, and evaluation/trace UI sources. The matrix is a project-authored priority statement, not external demand evidence.
- This report recommends a flow and measurable acceptance checks; it does not claim the Evaluation Lab is implemented or validated.
