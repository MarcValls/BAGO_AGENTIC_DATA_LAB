# Domain conformance F-003 implementation status

**Status:** `VERIFIED` for the ADL canonical reconstructed manifest adapter on branch
`codex/adl-domain-conformance-f003-20261029`, based on
`ae8e53e14afa763f816eac9e11ddc0e8a24cdc56`.

## Delivered

- A read-only adapter in `src/contracts/domain_conformance.py` that rejects a
  self-declared `CONFORMANT` packet unless the host-owned required controls
  map to checks recorded as PASS in a canonical, candidate-bound ADL teamctl
  handoff.
- Negative and positive synthetic regression vectors in
  `tests/contracts/evidence/test_domain_conformance.py`.
- Preservation coverage for the existing delivery-review/teamctl evidence
  path.
- `docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json` and
  `03_DOMAIN_CONFORMANCE_TEST_v1.0.md` were created as the current canonical
  originals on 2026-10-29 from requirements supplied in the conversation.
  They are not recovered historical bytes.
- The adapter validates the created manifest schema and 13 mandatory controls.
  It does not determine whether a mapped check is semantically sufficient.

## Verification evidence

- Focused manifest/adapter plus delivery-review preservation: **34 passed**.
- WhatsApp DOM transport preservation after installing the locked frontend
  dependencies: **28 passed**.
- `python scripts/generate_dynamic_readme.py`: full suite **1683 passed**;
  README generated on 2026-10-29 with exit code 0.
- `python scripts/generate_dynamic_readme.py --check --skip-tests`: **PASS**;
  1686 tests collected, suite not run by this check.
- The initial focused task controller closed `PASS` for the normalized adapter
  cut. A second controller attempt hit its 600-second limit while supervising
  README generation; the same generator then completed directly with exit code
  0. The timeout is a controller limit, not a test failure.

## Still open

- Historical byte-for-byte compatibility is `NOT_RUN`: the old source files
  were not found. The user authorized the newly authored v1.0 contract as the
  current canonical original for this ADL integration.
- Runtime activation/production integration is `NOT_RUN`; no domain activation
  is performed by this library adapter.
- Semantic adequacy of each host control-to-check mapping remains a host policy
  responsibility and requires its own reviewed checks.
- Remote CI and publication are pending.
