# DOMAIN CONFORMANCE TEST v1.0 — ADL canonical replacement

**Status:** canonical replacement authored 2026-10-29 under the user's
instruction to create the missing originals. It reconstructs the requirements
provided in the conversation; it is not a recovered copy of historical source
bytes. Schema: `05_DOMAIN_MANIFEST.schema.json` in this directory.

## Conformance controls

Every listed control is mandatory. `N/A`, missing evidence, or a producer's
own assertion is not a passing result. A control passes only when ADL's
independent verifier finds the corresponding host-required check in a valid,
candidate-bound execution handoff.

| ID | Control | Required assertion |
| --- | --- | --- |
| AUTH-001 | Authority | Domain cannot change kernel or execution authority. |
| SCOPE-001 | Scope | Positive and negative scope are explicit. |
| SOURCE-001 | Source roles | Canon, state, evidence, reference, memory, inference and experimental sources remain distinguishable. |
| STATE-001 | State and validity | Current, superseded, invalid and unknown are not conflated. |
| OPER-001 | Operations | Operations declare effects and required evidence. |
| CAP-001 | Capabilities | Claimed capabilities map to host-observed checks and limits. |
| EVID-001 | Evidence | Claims link to independently verified evidence references. |
| MEM-001 | Memory | Memory is historical context and cannot silently become current authority. |
| ROUTE-001 | Routing | Positive and negative routing cases are both checked. |
| REL-001 | Inter-domain relations | Handoff/dependency targets and versions are explicit. |
| VER-001 | Versioning | Superseded versions remain identifiable; compatibility is explicit. |
| SEM-001 | Semantic interface | Required query/inspection operations are declared. |
| KERNEL-001 | Kernel collision | No domain operation overrides kernel-owned policy or execution controls. |

## Decision rule

`CONFORMANT` is a binary result. It requires exactly one `PASS` for each of the
13 control IDs, at least one evidence reference per control, no open critical
conflicts, and no extra control IDs. `FAIL`, `BLOCKED`, `N/A`, missing,
duplicate, unknown, candidate-mismatched, or unverified controls prevent the
result. Quality scores or percentages cannot override a mandatory failure.

The JSON Schema enforces the minimum structural conditions for a conformant
claim. It cannot authenticate evidence, guarantee uniqueness of control IDs,
or establish that an evidence item proves its claim. The semantic verifier
must enforce the exact control set and resolve every evidence reference
against ADL's canonical managed execution records. Schema acceptance alone
never proves conformance.

## Negative vectors

1. `CONFORMANT` with no controls: reject at schema validation.
2. `CONFORMANT` with fewer than the 13 required control IDs: reject semantic validation.
3. Any mandatory control `FAIL`, `BLOCKED` or `N/A`: reject.
4. Missing, duplicated or unknown control ID: reject.
5. Empty, invented or producer-only evidence reference: reject unless the
   host mapping resolves it to a required passing managed check.
6. Candidate digest mismatch or open critical conflict: reject.
7. A valid candidate-bound handoff with every host-required check passing:
   accept only as a read-only conformance conclusion; it grants no permission
   and activates no domain.

## Scope note

This version defines ADL's accepted manifest contract for this integration.
Existing integrations that consume other source formats require an explicit
adapter and a separate compatibility test.
