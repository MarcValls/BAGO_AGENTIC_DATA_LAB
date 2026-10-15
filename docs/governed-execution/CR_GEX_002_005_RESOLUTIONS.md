# CR-GEX-002/003/004/005 — Decision record for v1 (fail-closed)

**Status:** RESOLVED_AS_CONTRACT_PROFILE / RUNTIME_NOT_IMPLEMENTED
**Source:** main `bdf2be825cfd16b3a9b9435efcb7c2384309cf25`, candidate PR #59.
**Authority:** these are new bounded decisions, **not** retrospective claims of validated runtime.

## CR-GEX-002 — Authenticated identity

**Decision:** define a mandatory `PrincipalProvider` interface in the backend. It must derive subject, issuer, authenticated session ID/binding, authentication evidence, agent ownership and workspace membership from verified server authority. Client/LLM supplied `subject`, `principal_id`, `workspace_root` or `auth_strength` MUST be ignored; local Origin/CORS is not an identity mechanism. For a native Windows host implementation, a future security-reviewed bridge must bind a verified OS logon identity and private per-session secret/token to API/WebSocket requests with replay-resistant and CSRF-safe verification, session expiry, revocation, key rotation and caller isolation. A username or loopback socket alone is not acceptable.

**Selected v1 profile:** `AUTH_PROVIDER_UNCONFIGURED` => `UNAVAILABLE / FAIL_CLOSED`. An explicit auto-allow policy is not proof of authentication. Human approval requires its own authenticated actor and must bind to the exact request digest.

**Availability:** No authenticated `PrincipalProvider` is verified at `/ws/agents/run`. Do not deploy.

## CR-GEX-003 — Durable permit + evidence authority

**Decision:** choose **SQLite on a single local host with a local filesystem**, `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `synchronous=FULL`, `busy_timeout`, write transactions `BEGIN IMMEDIATE`. Require uniqueness of permit_id/request_id/request_digest/attempt_id, FK linkage, conditional `UPDATE permits SET ... WHERE state='ISSUED' AND uses=0 AND ... RETURNING ...` plus insertion of `PERMIT_CONSUMED` and `DISPATCH_INTENT` in the *same committed transaction*. Permit claims remain immutable and MAC/signed; usage state is separate mutable data.

Record a monotonic per-request sequence number under the same DB transaction. Hash-chain canonical ledger events with domain separation, retaining the previous-event hash and immutable payload digest. Use an OS-protected signing/key service (unconfigured => deny). SQLite/WAL and a hash chain do **not** prove external append-only immutability or multi-host safety.

Workers must consume durable permit *before* dispatch. A failure of the commit prevents dispatch. Recovery enumerates committed `DISPATCH_INTENT` without matching terminal receipt: mark `RECONCILIATION_REQUIRED` (or an explicitly proven no-effect failure), never retry uncertain effect automatically. A receipt and terminal transition must be persisted atomically or report the result unknown.

**Selected v1 profile:** one host, local SQLite, one workspace authority, no network shares, no horizontal distribution. Schema migration, independent process contention and crash/restart tests required before enabling.

## CR-GEX-004 — Adapter and isolation

**Decision:** v1 first slice permits only **one explicit, typed, read-only capability** for a backend-owned, immutable fixture file under a backend-owned workspace. Reuse `ExecutionGateway.execute` → `SandboxManager.execute` → typed `FilesystemRequest(READ)`, bounded size and read-only profile. Before binding permit, compare effective path and canonical fixture identity with the registry; repeat scope validation at dispatch. If local workspace may be mutated by an untrusted concurrent process or guarantees cannot be supplied, mark `UNAVAILABLE`, not OS-isolated. An immutable fixture is an explicit trust assumption, not a general filesystem read privilege.

Process execution, pytest on untrusted code, arbitrary filesystem writes, shell, external HTTP and all MCP outbound network effects are **`UNAVAILABLE / FAIL_CLOSED`** until a measured backend implements the required OS and egress controls. `NetworkMode.DENY` in a logical profile does not constitute a firewall.

**Selected v1 profile:** read-only trusted fixture, strictly local; no subprocesses; no outbound networking. This does not change availability of separately tested legacy L1 sandbox demos.

## CR-GEX-005 — UI/Decision Inspector authority

**Decision:** Decision Inspector remains a read-only projection of ledger/receipt states by `run_id`, `request_id`, `trace_id` and digest. The approval service is separate from the Decision Inspector and editable agent state; UI is never source of authorization or execution truth. Render UNKNOWN/UNVERIFIED/RECONCILIATION_REQUIRED on missing or conflicting evidence, not SUCCESS. No changes to the existing `/ws/agents/run` or its fail-closed behavior before authorized E2E tests.

**Selected v1 profile:** inspector integration `UNAVAILABLE` until read-only adapter over persistent receipts exists.

## Contract-consistency findings and corrections

1. Correct the state machine: policy `ALLOW` from `PROPOSED` can enter `APPROVED` **only** for explicitly eligible auto-allowed effects; `REQUIRE_HUMAN` goes to `AWAITING_APPROVAL`. `DENIED` is terminal.
2. A DENY before registered GEXRequest creation requires a `ProposalDenialReceiptV1` bound to `proposal_digest`, not a fake versioned request.
3. Consumption failure when storage is down cannot produce a durable receipt; fail closed without falsely claiming evidence.
4. `PermitV1` is signed **immutable claims**; `PermitUseStateV1` is mutable transactional state. MAC/signature is not `signed_by` metadata.
5. `RECONCILIATION_REQUIRED` is conservative after uncertain dispatch/receipt failure. No exactly-once effect guarantee from a queue.
6. `RFC 8785` must be independently verified with JCS reference cases, UTF-8, Unicode, numeric and key-order vectors; mere `json.dumps(sort_keys=True)` compatibility is insufficient.
7. All receipt and ledger references are correlated structurally; missing, tampered or mismatched receipt is not evidence of success.

## Gate verdict

The CR-GEX-002/003/004/005 architecture **is decided** for a narrow future v1 profile. The runtime implementations are **NOT VERIFIED**, so execution remains `UNAVAILABLE / FAIL_CLOSED`. Do not FREEZE the contract until the conformance suite has actually run and a separate reviewer validates the semantic decisions and remaining P0/P1 count.
