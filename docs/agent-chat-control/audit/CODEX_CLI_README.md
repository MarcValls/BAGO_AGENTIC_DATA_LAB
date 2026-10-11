# BAGO frontend audit pack for Codex CLI

This is a source snapshot for a manual, read-only frontend and API-contract audit. Start with `CODEX_CLI_PROMPT.md`.

## Run manually

1. Extract the ZIP to a dedicated directory.
2. Open PowerShell in that directory.
3. Run `codex` to start Codex CLI with the pack as its working directory.
4. Paste the instructions from `CODEX_CLI_PROMPT.md`.
5. Review `AUDIT_REPORT.md` produced by the CLI. The prompt asks it to inspect only; it must not edit application source or run tests/builds.

The packet contains no credentials, node_modules, Python environment, or runtime data. The running host app is currently at `http://127.0.0.1:8081`; provider status was `not_configured` when the packet was prepared. The running service is not required for the source-only audit.

## Snapshot identity

- Worktree base HEAD: `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`
- Branch: `codex/agent-chat-control-v1`
- The worktree had local modifications. The files in this ZIP are the exact packaged snapshot, not a clean commit claim.
- See `SHA256SUMS.txt` for per-file integrity hashes.
