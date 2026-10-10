# README generation contract

README.md is a generated projection of the repository, not a second source
of truth.

The generator combines:

- docs/readme_manifest.json for stable project decisions and phase metadata;
- .bago/canon/STATE.md for the current phase, lifecycle status and next block;
- .bago/canon/LAB_CONTRACT.md for target roles;
- .bago/canon/JOB_SKILL_MATRIX.md for the technical skill table;
- .bago/canon/JOB_SKILL_MATRIX.md for the strategic/soft skill table;
- the canonical root documents declared in docs/readme_manifest.json;
- the actual src/, tests/, docs/, evidence/ and scripts/ inventory;
- the operational sync agent definition and executor;
- agents/CATALOG_MANIFEST.json for the reference-only agent catalog;
- the public default branch;
- the complete pytest result, when generation is run without --skip-tests.

Commands:

    python scripts/generate_dynamic_readme.py
    python scripts/generate_dynamic_readme.py --check
    python scripts/generate_dynamic_readme.py --check --skip-tests

The --check --skip-tests mode collects pytest cases, including parametrized
cases, without executing them and verifies that the checked-in README is
exactly reproducible. It requires the project dependencies to import test
modules; install them with `python -m pip install -r requirements.txt` first.
The normal generation path executes the full suite before writing.

Do not edit README.md manually. If the README is stale, update the source
document or manifest that owns the claim, then regenerate it.

## Manual review at work closure

Use the generated README as an output, then review the complete rendered file
against its sources before closing work:

| README content | Authoritative source |
|---|---|
| Project description and phase definitions | `docs/readme_manifest.json` |
| Current phase, date, status, tests and next block | `.bago/canon/STATE.md` and the full test run |
| Target roles | `.bago/canon/LAB_CONTRACT.md` |
| Technical and strategic skills | `.bago/canon/JOB_SKILL_MATRIX.md` |
| Architecture, sync agent, catalog and checkout inventories | Declared manifests and current repository files |
| First-use video, captions, guide, input and trace | `first_user_tutorial` in `docs/readme_manifest.json` plus the referenced artifacts |

1. Update only the source document or manifest that owns the changed fact.
2. Ensure every declared artifact exists and every README link is repository-relative.
3. Run `python scripts/generate_dynamic_readme.py`; this runs the complete test suite and writes the passing count into the README.
4. Read the complete `git diff -- README.md` and check dates, branch, phase/status wording, test count, links, inventories and whether any section disappeared unexpectedly.
5. Run `python scripts/generate_dynamic_readme.py --check --skip-tests`. This confirms reproducibility and collects the current test count; it does not execute tests or independently prove that they passed.
6. Include both command results and the reviewed README diff in closure evidence.
