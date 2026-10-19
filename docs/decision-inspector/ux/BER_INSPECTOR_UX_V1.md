# Decision Inspector UX contract for BER v1

Status: **PREPARED design contract** for ADL candidate `585fe4635596b1bd253fb8ba6d5b736ebf133ee9` with W01 reuse map frozen as `decision-inspector-reuse-map-v1`. This document governs downstream UI work for the BER integration. It defines a read-only inspection experience; it does not grant approval or execution authority. It supersedes older UX guidance where repository identity or behavior differs.

## Information architecture

Keep the existing React/Vite Decision Inspector entry and its three views: **Decision**, **Trace**, and **Actions**. The selected agent run is the persistent context. Show the supplied run ID and, when present, BAGO BER source/runtime identity and BAGO execution/request/permit/receipt IDs as separate labeled values. Never make ADL's LocalTrace or legacy sandbox receipt look like BAGO authority.

Within Decision, present this hierarchy:

1. **Conclusion**: source-provided query, answer, run status and run ID. Label the answer as supplied by the run.
2. **Claims**: render only structured claims from the decision contract. Keep a claim with no evidence visible and label it unsupported. Do not split answer text or citations into inferred claims.
3. **Evidence**: show explicit claim/evidence relation, evidence reference, source identity, supplied snapshot/revision and freshness. Preserve unresolved references.
4. **Provenance**: show source, source snapshot/revision or fingerprint when supplied, run identity, and matching trace/event identity. Missing values say “Not provided”; do not synthesize identity or freshness.

Use a persistent run context and an explicit breadcrumb such as `Run <id> > Conclusion > Claim <id> > Evidence <id> > Provenance`. Opening a detail retains the parent selection. Back returns to the originating claim or conclusion and restores focus. A trace-to-claim/action link retains the event and run context and identifies missing correlations rather than guessing them.

## Conclusion and evidence interaction

Selecting a claim opens its text and the linked evidence list. Selecting an evidence item opens a detail panel with its source and snapshot fields. A source reference that cannot be loaded remains visible with its identifier and a missing/unavailable message. A claim with zero links says “No supporting evidence linked”; a citation on the run alone is not a claim relation.

Show evidence support/freshness as text labels in addition to visual styling:

- **Supported** only when an explicit relation and source-backed evidence are present.
- **Unsupported** when a structured claim has no supporting evidence link.
- **Missing** when a declared reference cannot be resolved.
- **Stale** only when supplied expected and actual snapshot identities conflict.
- **Contradictory** only when source/evaluation data explicitly identifies conflicting evidence; show both sources.
- **Unknown / not established** when the producer did not supply enough information.

Do not calculate confidence from retrieval rank, citation count, BER status or a green state. Show confidence only with a producer-supplied value and label its source; otherwise say “Confidence not provided”. Keep unsupported, missing, stale, contradictory and unknown distinguishable from an empty collection.

## Trace inspection

Order trace rows by supplied sequence and show event ID, kind, status, parent event and evidence references. Present sequence as chronology and parent links as declared causality. Preserve source status such as DENY, ERROR and unknown verbatim. A missing parent or sequence gap is a visible trace warning. Trace rows may navigate to a claim or action only when an explicit correlation exists; otherwise show “Correlation unavailable”. Jaeger is an optional projection only when a real correlation and reachable link are supplied. It is not canonical receipt evidence or authority.

## Proposed action and BER lifecycle

The Actions view is a read-only review path. Present each proposal in distinct lifecycle sections:

`Proposed > Eligible / capability > Authorization decision > Execution > Receipt`

- **Proposed** shows requested effect, target, arguments (subject to existing redaction), proposer and reason when supplied. It is intent only.
- **Capability / eligibility** show their independent source states. Availability does not mean eligible or authorized.
- **Authorization** shows decision, actor/channel, permit identity, scope and validity only when supplied by BAGO. `ALLOW` or a permit means permission, not execution. Never mint, widen or expose a BAGO permit in the browser.
- **Execution** is shown only from an authoritative BAGO execution outcome bound to the same request/permit. ADL proposal state, LocalTrace and legacy sandbox output cannot establish BER execution.
- **Receipt** is successful only when the BAGO receipt is present and identity-linked to the same request and, where supplied, permit/effect. A missing or mismatched receipt remains **unverified**; never show success from a UI click, authorization decision or status badge.

Do not add approve, reject, retry, execute, delete or other effect controls under this read-only contract. If a later approved product contract adds a control, it must call a BAGO-owned authorization/API boundary, keep authorization separate from execution, require an explicit review step, and render completion only from a matching authoritative receipt. `filesystem.delete` remains blocked and must not be shown as an available action.

## Loading, empty, partial and error states

- **Loading**: retain the page title and run context; announce “Loading decision data” or the specific panel through a polite live region.
- **No run / no data**: distinguish no runs from a run whose optional evidence, trace or actions were not supplied. Explain what source data is absent.
- **Partial**: keep available panels usable; mark each absent artifact “Not provided” or “Unavailable”. Never substitute zero, success or a fabricated example.
- **Stale**: preserve the selected run and source identity; label the mismatch and keep both compared identities visible.
- **Error**: scope the message to the failing request/panel, provide a keyboard-accessible retry when safe, and preserve parent navigation and selection.
- **Unverified**: use when execution or receipt identity cannot be established. Do not collapse it into failed or succeeded.

## Keyboard, focus and screen-reader requirements

- Use one page-level heading, semantic landmarks, ordered headings, lists for claims/evidence/events, and native buttons and links. No clickable `div` elements.
- Keep the existing view navigation as ordinary buttons unless full tab semantics, selected state, associated panels and arrow-key behavior are implemented. Provide accurate accessible names and selected/current state.
- All selection, drill-down, back, disclosure, retry and any future review control must work with Tab/Shift+Tab and Enter; Space activates buttons. No hover-only information.
- On drill-down, focus the detail heading and announce the selected item. Back restores focus to the originating link/control and same parent context.
- Use visible labels for IDs/status values and visible focus indicators. Color, icon and emoji cannot be the only status signal. Long IDs must wrap and remain selectable/copyable.
- Announce loading and completion politely; reserve assertive announcements for blocking errors. Avoid repeatedly announcing the full trace on rerender.
- Preserve zoom/reflow, sufficient contrast and reduced-motion preferences. Verify keyboard-only and screen-reader behavior manually in addition to DOM checks.

## Downstream acceptance criteria

- A user can traverse conclusion > structured claim > explicit evidence > provenance and return to the same run/parent.
- Proposed intent, eligibility, authorization, execution and receipt have separate labels and no state is inferred from another.
- Missing, unsupported, stale, contradictory, unknown, partial and unverified states remain explicit.
- Only source-supplied identities and values are rendered; BER authority is visually distinct from ADL projections.
- Trace chronology and causality remain distinct; absent correlations stay absent.
- Keyboard focus, restoration, accessible names, live status and screen-reader requirements above are implemented and manually reviewed.
- No UI action can invoke a BER effect under this read-only contract; delete remains unavailable.

## Repository-grounded implementation notes

The current Inspector model (`frontend/src/features/decision-inspector/integration/DecisionInspector.tsx`) maps run, retrieval, LocalTrace and action artifacts into Decision/Trace/Actions. It currently produces no structured claims from answer text, labels unlinked citations, and binds nested receipts to matching run IDs. Existing decision, trace and action types live under `frontend/src/contracts/`; shared status and shell components live under `frontend/src/features/decision-inspector/{shared,shell}`. These are reuse points, not proof that every requirement above is already implemented or accessible. W01's `docs/decision-inspector/inventory/BER_REUSE_MAP.md` owns the authority boundary; this UX contract does not alter it.
