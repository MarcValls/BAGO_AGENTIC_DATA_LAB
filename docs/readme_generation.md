# README generation contract

README.md is a generated projection of the repository, not a second source
of truth.

The generator combines:

- docs/readme_manifest.json for stable project decisions and phase metadata;
- .bago/canon/STATE.md for the dated, declared phase history and its decisions;
- .bago/canon/LAB_CONTRACT.md for target roles;
- .bago/canon/JOB_SKILL_MATRIX.md for the technical skill table;
- .bago/canon/JOB_SKILL_MATRIX.md for the strategic/soft skill table;
- the canonical root documents declared in docs/readme_manifest.json;
- the actual src/, tests/, docs/, evidence/ and scripts/ inventory;
- the operational sync agent definition and executor;
- agents/CATALOG_MANIFEST.json for the reference-only agent catalog;
- the L15 Jaeger capture declared in docs/readme_manifest.json;
- the public default branch;
- the local JSON named by `verification_record` in the manifest for the exact
  dated CI candidate, executed counts, commands, scope and evidence links;
- `frontend` in the manifest, checked against App, component, API and package
  entrypoints, for the app layers and startup instructions.

The verification record is versioned evidence, not a network lookup. The
renderer requires schema `bago.readme.verification.v1`, an observation date,
an exact CI commit SHA, scope and check-level evidence links. It fails when
that record or a declared frontend/tutorial/demo source is missing; it does
not replace missing evidence with an old CI URL or a locally collected count.

Commands:

    python scripts/generate_dynamic_readme.py
    python scripts/generate_dynamic_readme.py --check
    python scripts/generate_dynamic_readme.py --check --skip-tests

The --check --skip-tests mode collects pytest cases, including parametrized
cases, without executing them and verifies that the checked-in README is
exactly reproducible. It does not publish a passing count or test badge. It
requires the project test dependencies to import test modules; install them
with `python -m pip install -r requirements-test.txt` first. The normal
generation path executes the full suite before writing.

`passing_tests` remains in the `render_readme` helper signature for callers,
but intentionally does not affect the rendered content. Local pass/skip
counts can differ by platform. Both command modes render the same versioned
verification snapshot; a real local execution reports its result in the
terminal, without silently becoming the CI result for another candidate.

The opening order is purpose → frontend app/startup → tests and results →
local demo → architecture. A linked table of contents leads to these blocks.
Phase inventories, skills, historical videos/integrations and the complete
canonical-source index remain in `<details>` blocks. Folding changes the
reading hierarchy, not the evidence's lifecycle or its historical scope.

Do not edit README.md manually. If the README is stale, update the source
document or manifest that owns the claim, then regenerate it.

## Manual review at work closure

Use the generated README as an output, then review the complete rendered file
against its sources before closing work:

| README content | Authoritative source |
|---|---|
| Project description and phase definitions | `docs/readme_manifest.json` |
| Dated phase history and decisions | `.bago/canon/STATE.md`; not automatically refreshed by a documentation edit |
| Test results | Versioned JSON at manifest `verification_record`, with exact CI commit/date/scope/URLs; collection is not a test result |
| Frontend layers and startup | manifest `frontend`, `frontend/src/App.tsx`, linked components, `frontend/package.json`, `src/api/server.py` and launcher/setup guide |
| Target roles | `.bago/canon/LAB_CONTRACT.md` |
| Technical and strategic skills | `.bago/canon/JOB_SKILL_MATRIX.md` |
| Architecture, sync agent, catalog and checkout inventories | Declared manifests and current repository files |
| First-use video, captions, guide, input and trace | `first_user_tutorial` in `docs/readme_manifest.json` plus the referenced artifacts |
| Jaeger screenshot and measured L15 result | `jaeger_capture` in `docs/readme_manifest.json` plus `evidence/l15_otel_jaeger_live.md` |
| Demo artifact contract, roles and skills | `docs/readme_manifest.json`, `.bago/canon/LAB_CONTRACT.md`, `.bago/canon/JOB_SKILL_MATRIX.md`, and the linked demo guides |
| Bruma app walkthrough, order cases, receipts and no-action boundary | `business_demo` in `docs/readme_manifest.json` plus the generated app artifacts under `output/playwright/bruma-market-tutorial/` |
| Phase evidence inventory | `phases[].checks` in `docs/readme_manifest.json` resolved against files in the current checkout |

1. Update only the source document or manifest that owns the changed fact.
2. Ensure every declared artifact exists. Repository artifacts use relative links;
   execution evidence may link directly to the recorded CI run/job URL.
3. Run `python scripts/generate_dynamic_readme.py`; this runs the complete test suite before writing. The README does not convert the collected case count into a passing claim.
4. Read the complete `git diff -- README.md` and check dates, branch, phase/status wording, links, inventories and whether any section disappeared unexpectedly.
   Confirm the frontend and dated verification snapshot appear before the demo
   and architecture. Open the historical details: verify the Jaeger image and
   its 15-span / 13-operation summary against linked L15 evidence, every phase
   inventory/missing-pattern marker, role/skill tables and four Bruma decisions.
   Confirm that customer directories, invoices and delivery notes are outside
   the tutorial dataset. Old CI and AWS observations must remain historical;
   neither credit availability nor L15 runtime state is refreshed by rendering.
5. Run `python scripts/generate_dynamic_readme.py --check --skip-tests`. This confirms reproducibility and collects cases; it does not execute tests or prove that they passed.
6. Include both command results and the reviewed README diff in closure evidence.
