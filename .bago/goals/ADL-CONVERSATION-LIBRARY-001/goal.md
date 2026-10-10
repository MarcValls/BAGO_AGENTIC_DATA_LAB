# Goal: ADL Conversation Library v0.1

## Authority and scope

- User-authorized objective: persist conversations created inside BAGO Agentic Data Lab.
- Included owners: the ADL App Assistant and agents configured inside this ADL instance.
- Excluded: Codex conversations, imports from other chat systems, cross-project access, semantic retrieval over old chats, execution recovery/idempotency, and automatic promotion of conversation content into canonical memory.
- First delivery: Phase 0 freeze/reuse map plus Phase 1 local persistent MVP.
- Worktree: `%USERPROFILE%/AppData/Local/Temp/BAGO_AGENTIC_DATA_LAB_conversation_library`.
- Preserve every pre-existing dirty or untracked file. Do not modify `.bago/team/runtime/state.json`; its existing mission is already terminal `DONE`.

## Acceptance criteria

1. A conversation has a stable ID, one owner kind (`assistant` or `agent`), an owner ID, a project ID for this ADL workspace, timestamps, status, title, and revision.
2. Messages have stable IDs, server-assigned order, role, content, timestamp/status, and optional source/trace reference metadata. Credentials and provider secrets are never stored in the conversation database.
3. Backend storage is a dedicated SQLite database under the current user's local application data, separate from the repository, vector index, jobs, provider configuration, and LocalTrace stores.
4. The backend is authoritative for saved history. The UI sends a conversation ID for turns; it does not supply saved conversation history as authority.
5. App Assistant and each configured ADL agent have separate conversations. Selecting a different agent does not erase or replace the prior conversation.
6. The UI can start a new conversation, list recent conversations, reopen one without calling an LLM, rename, archive, soft-delete, and restore it.
7. A user/assistant exchange and its available sources/trace identifiers remain linked. Missing evidence is represented as absent; the library does not manufacture traces or verification claims.
8. Concurrent updates use a persisted revision or equivalent conditional update so stale edits cannot silently overwrite newer messages/metadata.
9. The acceptance workflow creates three assistant messages and two separate conversations for one agent, switches owners without loss, restarts the backend and browser, retrieves all three conversations and their identity/title/timestamps/messages, renames, archives, soft-deletes/restores, and verifies the resulting state.
10. Verification is performed at backend and real-browser levels. Provider-free persistence checks are included; an LLM is not required to browse/reopen stored chats. Report any unrun criteria explicitly.

## Execution plan

### Phase 0 — freeze and reuse map

- Record the exact worktree HEAD, branch, remote-main comparison, and pre-existing dirty-state fingerprint.
- Materialize `PHASE_0_REUSE_MAP.md` with responsibilities classified as REUSE, EXTEND, or NEW.
- Confirm no existing chat, evidence, or vector-store owner is duplicated.

### Phase 1 — persistent library MVP

- Add a dedicated conversation domain module, SQLite repository/schema initialization, and API routes.
- Persist messages and references through server-owned conversation IDs.
- Adapt AgentChat to manage separate assistant/agent conversations and library controls.
- Implement archive, logical delete, and restore.
- Verify persistence and the browser recovery workflow against the acceptance criteria.

## Baseline freeze (before goal files)

- HEAD: `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc` (`feat: Implement Ollama provider integration with UI for model selection and authentication`).
- Branch: `codex/agent-chat-control-v1`.
- Remote `main` observed by `git ls-remote`: `78e4d9ff2bc69b4cda6352fedfe5df4c9adbf743`.
- Merge base: `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`; divergence is one local-only and one remote-only commit.
- Pre-existing tracked diff SHA-256 (`git diff --binary HEAD`): `9bb0259e8730ec77d7427b1b9ff4c3e235b12f278b2193de7cd8a9f9540105b4`.
- Pre-existing `git status --short --untracked-files=all` stream SHA-256: `3256bedc478acd6ab53c2d08ce830c93af9dd32b3c24495fbf00e274e2606c53` (46 status entries at capture).
- The current status includes edits/evidence from prior authorized chat, runner, trace, and frontend-audit work. Those changes are not owned by this goal and must remain intact.


## Active worktree

- Path: `%USERPROFILE%\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_conversation_library`
- Branch: `codex/conversation-library-v1`
- Base HEAD: `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`
- Reused chat-control changes were ported from the preserved `codex/agent-chat-control-v1` worktree; `.bago/team/runtime/state.json` and runtime/provider data were excluded.

## Phase 1 result

- Implementation and closure evidence: `PHASE_1_VERIFICATION.md`.
- Final candidate remains an uncommitted worktree diff on the base HEAD above; no commit, push, merge, or synchronization was performed.

## Proposed next objective

Support two agent lifecycles:

1. **One-shot agent:** created for one bounded user-requested task, then completed.
2. **Signal-waiting agent:** registered with an explicitly configured trigger, stays waiting, and activates when that signal arrives.

This is feasible, but remains `PROPOSED`. Before implementation, define signal sources/event types and the authorization, lifetime, idempotency, retry, cancellation, and audit rules. Do not imply an agent is continuously monitoring anything until a real trigger source and runtime are implemented and verified.

