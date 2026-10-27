# README generation contract

README.md is a generated SVG-only visual landing, not a second source
of truth. README_DETAILS.md is the full generated technical reference at the
repository root, preserving the relative URLs and comprehensive evidence.

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
  entrypoints, for the app layers and startup instructions;
- `presentation` in the manifest for the brand banner, current capture inventory
  and its dated provenance guide, plus `docs/readme_frontend.md` for drill-down.

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
cases, without executing them and verifies both checked-in README variants. It does not publish a passing count or test badge. It
requires the project test dependencies to import test modules; install them
with `python -m pip install -r requirements-test.txt` first. The normal
generation path executes the full suite before writing.

`passing_tests` remains in the `render_readme` helper signature for callers,
but intentionally does not affect the rendered content. Local pass/skip
counts can differ by platform. Both command modes render the same versioned
verification snapshot; a real local execution reports its result in the
terminal, without silently becoming the CI result for another candidate.

## Corporate landing and progressive detail

The current presentation follows the user's explicit request for an extensive,
visual corporate BAGO README. Its principal sections remain visible: laboratory,
chat-led frontend, fresh screenshots, data, agents/tasks/evaluation, providers,
governed execution, architecture, demos, executed verification, installation,
observability, capability status and documentation. Each section contains a
substantive overview, a table or figure, and its own deep documentation links.
There is no compact line-count limit. Historical inventories and matrices may
use disclosure blocks; core product sections must not be hidden inside them.

Chat is the main product entrypoint. Describe implemented chat controls and
embedded views separately from the direction of making more workflows available
conversationally. Never claim complete conversational coverage from navigation
callbacks alone. The frontend guide documents remaining manual steps and the
runtime/provider/authorization conditions of each route.

`presentation` in the manifest owns the corporate banner, frontend guide and
fresh screenshot inventory. Images use local repo assets and meaningful alt
text. The banner extends the actual BAGO brand assets. Screenshots must be newly
captured from the documented running app in a visible browser, with observation
date, server/build identity, actual navigation, scope and hashes in their capture
guide. The renderer rejects absent presentation artifacts. Old tutorials remain
historical linked documents; their captures must not be embedded as current UI.
A screenshot proves only its documented observation, not a new provider call,
tool effect or integration validation.

The 2026-10-22 capture session additionally records a new real agent creation,
an explicit authorized read of a synthetic `DEMO.md`, and a provider response
under trace `trace-496fac766f384348`. Keep that execution distinct from the
captured Inspector, which displayed older Bruma trace `trace-5b385699ffda0529`.
Do not promote navigation to an end-to-end Chat-to-Inspect PASS. The visible
`model_registration_mismatch` failure and the subsequent verified model setup
remain part of the demonstration. A UI excerpt hash identifies its numbered
excerpt; the complete input-file hash identifies different bytes.

The SVG landing contains nine versioned 1200-pixel-wide panels under
`docs/assets/readme-banner/`, composed from `docs/readme_svg_manifest.json`.
Every visible title, diagram, command, card and grid in README.md is drawn
inside SVG; the README itself contains only linked image elements.

The complete, accessible narrative, tables, Mermaid, screenshots,
source provenance and dated verification remain in `README_DETAILS.md`,
generated by the original `render_readme()` helper. Each visual panel links
to a substantive technical document. Vector panels are conceptual
summaries, not runtime screenshots or evidence of a new execution.

The generator validates local paths, parses SVG XML, rejects unsafe
elements/references, and checks exact reproducibility of both generated
READMEs. GitHub sanitization may affect layout and image spacing; visually
review actual GitHub desktop/mobile rendering separately. A passed static
check does not certify pixel rendering or frontend behavior.

Do not edit README.md or README_DETAILS.md manually. If the README is stale, update the source
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
| Current screenshot gallery | `presentation` in the manifest and the current capture guide with identity and hashes |
| Historical measured L15 result | `evidence/l15_otel_jaeger_live.md`; historical image remains in its original documents |
| Demo artifact contract, roles and skills | `docs/readme_manifest.json`, `.bago/canon/LAB_CONTRACT.md`, `.bago/canon/JOB_SKILL_MATRIX.md`, and the linked demo guides |
| Bruma app walkthrough, order cases, receipts and no-action boundary | `business_demo` in `docs/readme_manifest.json` plus the generated app artifacts under `output/playwright/bruma-market-tutorial/` |
| Phase evidence inventory | `phases[].checks` in `docs/readme_manifest.json` resolved against files in the current checkout |

1. Update only the source document or manifest that owns the changed fact.
2. Ensure every declared artifact exists. Repository artifacts use relative links;
   execution evidence may link directly to the recorded CI run/job URL.
3. Run `python scripts/generate_dynamic_readme.py`; this runs the complete test suite before writing. The README does not convert the collected case count into a passing claim.
4. Inspect `git diff -- README.md README_DETAILS.md docs/assets/readme-banner/` and review the rendered pages.
   Require visible substantial product sections, a chat-led entry narrative,
   accessible corporate branding, fresh screenshot provenance and a resolved
   deep link from each principal section. Confirm actual chat controls are
   distinct from manual steps and future coverage. Review every phase inventory,
   missing-pattern marker, role/skill table and four Bruma decisions in the
   appendices. Customer directories, invoices and delivery notes remain outside
   that dataset. Old CI, AWS and L15 observations retain their candidate/date;
   none is refreshed merely by rendering the README. A current app screenshot
   does not validate a new inference or effect.
5. Run `python scripts/generate_dynamic_readme.py --check --skip-tests`. This confirms reproducibility and collects cases; it does not execute tests or prove that they passed.
6. Include both command results and the reviewed README diff in closure evidence.

## Additional vector-specific acceptance

- Panels are safe, standalone SVG graphics (no scripts, raster, external
  resources or `foreignObject`), with local links and alternative text.
- README.md contains no visible Markdown prose or Markdown tables.
- README_DETAILS.md retains all original source-bound material and links.
- Both generated files must match the source-driven renderer.
- Visual QA on GitHub is a separate check; do not call it PASS if NOT_RUN.
