# README generation contract

README.md is a generated projection of the repository, not a second source
of truth.

The generator combines:

- docs/readme_manifest.json for stable project decisions and phase metadata;
- STATE.md for the current phase, lifecycle status and next block;
- LAB_CONTRACT.md for target roles;
- JOB_SKILL_MATRIX.md for the technical skill table;
- the canonical root documents declared in docs/readme_manifest.json;
- the actual src/, tests/, docs/, evidence/ and scripts/ inventory;
- the operational sync agent definition and executor;
- the public default branch;
- the complete pytest result, when generation is run without --skip-tests.

Commands:

    python scripts/generate_dynamic_readme.py
    python scripts/generate_dynamic_readme.py --check
    python scripts/generate_dynamic_readme.py --check --skip-tests

The --check --skip-tests mode is dependency-light: it counts test functions
from the source tree and verifies that the checked-in README is exactly
reproducible. The normal generation path executes the full suite before
writing.

Do not edit README.md manually. If the README is stale, update the source
document or manifest that owns the claim, then regenerate it.
