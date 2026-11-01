# Backend CSV: implementation and boundary checks

Base: `16b74a590889d6b42d7889abc8cd114b35c5dbf1` (merged PR #112).
This report concerns main-chat reads. Table/Text rendering is a separate feature.

## IMPLEMENTADO

- Existing `WorkspaceReadAuthorizations` now supports an optional CSV request
  fingerprint, project/binding/policy identity, metadata identity, revocation and
  bounded effect leases. Legacy and CSV grants cannot be cross-promoted.
- Issuance requires the main assistant, an active owned conversation, saved READ,
  one exact relative CSV, the question and parsing options. It reads metadata only.
- `/api/chat/control` consumes the grant once. `workspace_read` reads the bounded
  original bytes under the existing saved-policy lease. No RAG ingestion, corpus
  import, new permission store, generic file authority or writing is introduced.
- IO and successful conversation append hold the existing policy, teamctl STOP
  and grant locks in that order, rechecking after waits. They never hold those
  locks during model inference. Revocation acknowledges after an already-running
  bounded effect completes; subsequent effects are denied. A provider request
  already dispatched cannot be retroactively unsent; its result is withheld if
  the grant, policy, conversation or STOP changes before publication.
- STOP uses the fixed shipped controller, not executable code from a selected
  project. An existing PAUSED or unverifiable mission blocks this CSV route.
  An absent mission creates no new one. This is not global STOP integration for
  other ADL routes.
- Before, during and after reading, file metadata detects replacement and
  in-place changes. Before publication it also checks project, binding, policy,
  conversation/revision, grant lifetime/revocation and file identity again.
- The shipped toolkit parses the complete CSV. The selected provider proposes
  only a bounded `query_csv` plan. Toolkit Decimal calculations and the renderer
  produce the answer; no second model invents numerical results. The displayed
  formula/filter/locale remains reviewable because a valid plan is not proof of
  semantic agreement with the user's question.
- Responses persist actual source rows, source locations, complete-input
  coverage, file/plan/result SHA-256, read receipts and structured `csv_analysis`
  in the existing conversation. Failures expose fixed diagnostics, not raw
  provider text or withheld cell contents.

Limits remain 256 KiB and 250 physical lines. The parser additionally bounds
columns/cells; the query engine bounds expression complexity and output. A
display limit does not truncate the data used for aggregates. Invalid numeric
formats, malformed CSV and unknown columns fail explicitly.

## VERIFICADO at W02

`tests/test_csv_chat_access.py`, `tests/test_workspace_read.py`,
`tests/test_document_tools_integration.py`, and
`tests/project-permissions/backend/test_chat_saved_read_policy.py`:
**57 passed** on Linux/Python 3.12 with pinned test dependencies.

The new tests use a real temporary filesystem, saved READ policy, grant registry,
locks and toolkit. Only provider interpretation is controlled. They include:

- The original 183-byte fixture and its SHA-256; independently expected row
  amounts 199.80, 54.00 and 47.50, pending 247.30, total 301.30; bytes/metadata
  unchanged after successful analysis.
- Missing, expired, revoked and already-used grants; wrong owner, conversation,
  revision, question, path and parsing options; exact-path confinement despite
  a broader saved READ directory.
- External/traversal paths; file replacement/in-place changes; policy/binding
  changes; cancellation and STOP; malformed/oversized input and invalid plans.
- Real concurrent waits: revoke/expiry/STOP while waiting for the policy lease
  denies both IO and publication. Acknowledged revocation serializes with the
  existing grant's bounded effect lease.
- Existing text reading, saved READ and document-tool integration regressions.

### Preserved review finding: CSV-AUTH-WAIT (P1, corrected)

The independent preliminary review reproduced an authorization check made before
a wait on the policy lock. Revoking during that wait still allowed the original
implementation to read bytes; later checks withheld the result and prevented
provider dispatch. This was a real IO authorization defect.

The correction intersects the existing locks at IO/publication and checks
authority after waits. The reviewer independently repeated six cases (revoke,
expiry and STOP at each boundary): no effect, no provider dispatch for denied
reads, precise error code. Regression tests preserve those sequences. Formal
HTTP verification follows in W12; this report does not replace it.

## NOT_RUN here

Real-provider semantic interpretation, the user's Windows/Brave installation and
production deployment. Formal HTTP F10–F12 reproduction and browser evidence
are reported separately under `review/` and `frontend/`. A passing Table view is
not evidence of a main-chat read.
