# Submodule inventory and candidates

**Review date:** 2026-10-07
**Scope:** local `BAGO_AGENTIC_DATA_LAB` checkout and the directly related local BAGO memory-MCP copy.
**Purpose:** record existing submodules and evaluate local components that could become independently versioned repositories. This inventory does not add or initialize submodules.

## Current Git state

- This checkout has no `.gitmodules` file.
- `git ls-files -s` contains no mode `160000` entries (Git submodule gitlinks).
- `git submodule status` reports no initialized submodules.
- A recursive scan of this checkout, pruning `.git`, virtual environments, Node dependencies, caches, and build output, found no nested Git repository.
- Current branch: `real-world/openmetadata-28860-v1.1`.

Therefore, **there are currently no submodules whose commits need pinning**. Git pins a submodule by storing the checked-out commit as a `160000` gitlink in the parent commit; `.gitmodules` records its path and clone URL. A branch name or tag in `.gitmodules` is not the pin.

## Local candidate register

| Candidate | Local evidence | Assessment | Current pin |
|---|---|---|---|
| `frontend/` portfolio UI | `frontend/package.json` identifies `bago-portfolio-ui` (React/Vite). `Dockerfile.ui`, `docker-compose.ui.yml`, and `docs/agent_builder_ui.md` describe it as part of this demo and its API. No nested `.git` or independent remote was found. | **Keep in this repository for now.** It is a separable UI component, but its documented build and runtime use the root API/demo artifacts. Extract only if it gains an independent release/build contract. | None; not a repository. |
| `src/api/` and `src/jobs/` | Local directories referenced by the UI/API implementation and Docker setup; no nested Git metadata found. | **Do not make submodules.** They are the server-side half of the same feature and need to evolve with this checkout. | None. |
| Proposed repository `ia_memoria_mcp_inline` (current local path: `BAGO/backend/tools/ia_memoria_mcp_local/`) | Exists in sibling local checkout `../BAGO`. `git -C` from this directory resolves to the enclosing `BAGO` repository; the copied MCP directory is not an independent Git root. `BAGO` has remotes `origin=https://github.com/MarcValls/BAGO.git` and `bago0=https://github.com/MarcValls/BAGO_0.git`; local HEAD observed during review: `8ac47eff1d5a11982642888154272b5375b39d6f`. | **Strong candidate for an independent repository, not yet a submodule.** Use the requested repository name `ia_memoria_mcp_inline`. It currently has no standalone repository/commit to pin. Before creating it, decide public/private contents and release contract, and exclude user memory data from publishable source. Then record an immutable commit before adding it as a submodule. | None for the MCP directory. The enclosing BAGO commit is not an MCP-specific version. |
| `../BAGO` as a whole | Separate local Git checkout with the `MarcValls/BAGO` remote; local state was dirty and ahead of its tracked branch at review time. | **Do not embed as a submodule here.** It is a separate product/repository with its own canon and state. Coordinate repositories at a GitHub Project or documentation/hub level unless this demo acquires a concrete build-time dependency on a specific BAGO commit. | Separate repo HEAD observed above; not a submodule pin. |
| `portfolio/day1-inventory/` | Its README says the inventory package was moved to a user Documents directory and this folder is a pointer. No nested Git metadata found. | **Not a submodule candidate** based on current checkout evidence. It is a pointer to local material, not a self-contained tracked repository. | None. |

## Pinning procedure when a candidate is ready

1. Create or identify the candidate's standalone repository and decide whether its source and data are appropriate for that repository's visibility.
2. Select and review a specific commit in that repository. Record the full commit SHA in the review notes; do not rely on a moving branch name.
3. Add it with `git submodule add <clone-url> <path>`, then check out the reviewed commit inside the submodule directory.
4. Commit both `.gitmodules` and the parent repository's gitlink. The gitlink is the actual commit pin; `.gitmodules` supplies the URL and path.
5. Verify with `git ls-files -s` (expect mode `160000`), `git submodule status`, and a fresh clone followed by `git submodule update --init --recursive`.
6. Update a submodule by checking out and reviewing a new commit inside its directory, then committing the changed gitlink in the parent. Do not claim a branch setting in `.gitmodules` pins an immutable version.

## Review boundary

This is a local inventory, not an authorization to publish, split, move, or add repositories. The current checkout contains unrelated uncommitted and untracked work; it was preserved. No candidate was initialized or changed, and no submodule was added.
