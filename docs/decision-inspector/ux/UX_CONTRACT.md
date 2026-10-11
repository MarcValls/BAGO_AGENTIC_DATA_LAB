# Decision Inspector UX contract v1

Status: design contract, grounded in the repository inventory at HEAD `c87f619d4a167bca854de4bbda75e2574c076c75` and inspected React components. This is not a claim that these interactions are implemented.

## Product surfaces and information architecture

Keep the existing React/Vite shell and its Summary, Retrieval, Authorization, Trace and Evaluation views. Decision inspection is a cross-view reading model, not a second evidence store. Use the selected run as the persistent context; identify it by the existing `agent_run.run_id` and expose the associated LocalTrace `trace_id` where available.

Within a selected run, order information as:

1. **Conclusion** — show the agent answer and run status from Summary. Label this as the agent's conclusion, and keep the originating query and run identity visible.
2. **Claims** — show claim-sized statements beneath the conclusion only when a source provides them. The current `AgentRun`/artifact UI exposes `answer` and `citations`, but the inspected components do not expose a structured claim collection. Until a contract supplies claims, label citations as citations; do not fabricate claim nodes or imply that a citation proves the whole answer.
3. **Evidence** — link each supported claim to its explicit evidence references. Retrieval already exposes document/chunk IDs, ranking scores and citations; LocalTrace events carry `evidence_refs`. Make the evidence source and reference inspectable and retain the parent claim/conclusion context.
4. **Provenance** — show the originating run, source/document or event reference, trace/event identity and available revision/snapshot metadata. `LocalTrace` provides trace/run IDs, event IDs, sequence, parent-event ID and refs. If a snapshot/revision is not supplied by the source, show “Not provided”; never infer one.

Use a stable breadcrumb or back link such as `Run <run_id> → Conclusion → Claim → Evidence → Provenance`. Opening a detail must preserve the selected run and the parent item; Back returns to the exact parent and selection. Cross-links to Trace should retain the originating evidence reference and scroll/focus the matching event when it exists.

## Evidence and uncertainty states

Every conclusion/claim/evidence relationship must communicate support state in text as well as color:

- **Supported**: at least one explicit evidence reference resolves to an available source.
- **Unsupported**: the claim has no evidence reference. Keep the claim visible, state “No supporting evidence linked”, and avoid a success badge.
- **Missing**: a reference is declared but its record/source is unavailable. Display the unresolved reference and an explanation; do not silently drop it.
- **Stale**: source snapshot/revision is older or does not match the selected run's declared context revision. Show both identities and “Freshness not established” when comparison metadata is absent.
- **Contradictory**: the available source/evaluation explicitly reports conflicting evidence. Keep both sides and their provenance visible; do not resolve the conflict in presentation.
- **Unknown**: the producer did not provide enough data to determine support/freshness. Distinguish this from a negative finding.

Current retrieval UI exposes ontology contradiction count and references, but a zero count only means that this field reports zero; it is not proof that all answer claims are contradiction-free. Do not calculate confidence from retrieval rank/score. Render confidence only if the producer provides a defined value and meaning; otherwise “Confidence not provided”.

## Proposed action, authorization, execution and receipt

The Authorization view already renders tool proposals, decision, effect type, outcome, permit/request IDs and provider/sandbox receipts. Preserve an explicit lifecycle with separate labels and timestamps/identifiers when supplied:

`Proposed → Authorization decision → Execution → Receipt`

- **Proposed** describes requested intent and rationale; it does not mean approved or run.
- **Authorization** shows ALLOW/DENY/other decision and permit ID. ALLOW is permission, not evidence of execution.
- **Execution** is shown only when the source reports that the call/effect occurred (`called`/actual effect or execution outcome). Do not infer it from a permit or proposal.
- **Receipt** is the immutable outcome evidence, linked back by proposal/request/permit/receipt IDs. Missing receipt stays “Receipt not available”; do not display success without receipt evidence.

Keep read-only and mutating effect types visible. Any future approve/reject action must be an explicit, keyboard-operable control with a confirmation/reason path and clear pending/denied/authorized/executed result; this contract defines display and interaction semantics, not new execution authority. UI actions must call existing governed API/authorization boundaries, never bypass them.

## Loading, empty, partial and error states

- **Loading**: announce “Loading run artifacts” via a polite live region; keep page title and selected run context stable. For slower loads, use a textual status in addition to a spinner.
- **Empty**: distinguish “No runs/artifacts exist” from “This run has no evidence/proposals/events”. Explain the next available navigation without inventing sample records.
- **Partial**: render available panels and mark each absent artifact “Not provided” or “Unavailable”; do not turn optional missing data into zero or success. Keep errors scoped to the failed panel when possible.
- **Error**: state which request/resource failed, preserve retry/back navigation, and expose a retry control. Avoid telling users to run `demo.py` as the only remedy unless that is actually appropriate to the selected runtime.
- **Stale**: retain visible data with its run/snapshot identity and a stale label; never silently replace or merge artifacts from different runs.

The current App has top-level loading, error, and “No data” branches around `/api/artifacts`. The contract asks implementations to make these accessible and distinguish no data from partial data; it does not assert those distinctions exist today.

## Keyboard, focus and screen reader

- Use semantic landmarks, one page-level heading, ordered section headings, native buttons/links, and lists for claims/evidence/events. Do not use clickable `div` elements.
- Implement the existing top-level view selector as an accessible tab pattern only if it provides tab semantics, arrow-key movement, selected state and associated panels; otherwise use ordinary navigation links/buttons with accurate names.
- All drill-down links and action controls must be reachable in logical reading order by Tab/Shift+Tab. Enter activates links/buttons; Space activates buttons. Do not require pointer hover.
- On navigation to a detail, move focus to its heading and announce the selected item. Back returns focus to the originating link. Expanding evidence details must use a native disclosure or equivalent `aria-expanded` control.
- Give every control a visible label; associate field labels and status text with their values. Do not rely on emoji, color, icon, or abbreviated badge text alone.
- Announce loading and asynchronous completion politely. Use an alert/live assertive announcement for blocking errors only. Avoid announcing each timeline row on every render.
- Preserve visible focus indicators, sufficient contrast, zoom/reflow, and reduced-motion behavior. Long IDs should remain selectable/copyable and be read as labeled values.
- Validate manually with keyboard-only navigation and a screen reader; automated DOM checks alone do not establish usability.

## Trace and Jaeger boundary

Use LocalTrace as the evidence-bearing local timeline: order by `sequence`, preserve `event_id`, `parent_event_id`, kind/status and evidence refs. Keep causality (parent relationship) distinct from display chronology. Jaeger is an OTLP projection useful for backend span inspection; it is not execution authority, canonical evidence, or proof of React behavior. The W01 inventory found no UI-linked Jaeger URL/correlation contract, so show a Jaeger link only when a real correlation identifier and reachable trace URL are provided; otherwise show the local trace identity and “Jaeger correlation unavailable”. A browser screenshot of the dashboard and a Jaeger trace screenshot are separate evidence artifacts.

## Implementation acceptance checklist for downstream UI work

- User can follow conclusion → (available) claim → evidence → provenance and return to the same parent/run.
- Missing/unsupported/stale/contradictory/unknown states are explicit and not collapsed into empty arrays or green status.
- Proposal, authorization, execution and receipt are visually and semantically distinct; no approval implies execution.
- Loading, empty, partial and error states have accessible text and suitable recovery/navigation.
- Keyboard path, focus restoration, labels, live announcements and screen-reader semantics are implemented and manually checked.
- UI renders only source-backed values; no fixture/demo record is presented as a real run.
- Jaeger links/captures are treated as projections and are not substituted for LocalTrace or browser UI evidence.
