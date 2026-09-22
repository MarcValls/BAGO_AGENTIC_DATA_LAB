# Workspace Binding Contract

`WorkspaceBinding` is the context identity boundary for governed agent work.
It answers **where the agent is operating** before a proposal can be considered
for authorization. It does not grant permission to create, write, delete, or
call an external API.

## Canonical claims

Each binding contains:

- `workspace_id`: stable, local identifier derived from the canonical checkout;
- `repository_root`: resolved Git worktree root;
- `repository_identity`: credential-free `host/owner/repository` identity from
  the configured remote, or a local fallback when offline;
- `branch` and `commit_sha`: the Git snapshot that produced the binding;
- `context_revision`: the BAGO context/canon revision used for reasoning;
- `fingerprint`: SHA-256 over all claims above except the root path.

## Invariants

`WorkspaceBinding.from_git(...)` performs read-only Git inspection and rejects
missing repositories, empty context revisions, invalid Git revisions, and
repository mismatches. `assert_in_scope(path)` resolves a target and rejects
path traversal or symlink escapes outside `repository_root`.

`workspace_binding_is_governed(binding)` verifies the claims and, by default,
checks that the current Git identity still matches the binding. A valid binding
is necessary context evidence; it is not a `Permit` and cannot authorize a
material effect.

## L9 execution boundary

The L9 `file_creator` proposal now generates a real contract test using this
module. The proposal still remains behind `REQUIRE_HUMAN` until a caller has a
valid permit for the file effect.
