# ADL domain conformance adapter v0.1

**State:** implemented as a read-only library adapter for ADL's canonical
reconstructed manifest v1.0. Historical source bytes were unavailable; this
contract was authored from the requirements supplied in the conversation and
accepted as the current original for this integration.

## What it does

`src/contracts/domain_conformance.py::verify_domain_manifest` validates the
canonical manifest and its exact 13-control set, then evaluates it against a
host-supplied required-control/check map. The lower-level
`verify_domain_conformance` also accepts ADL-normalized packets.
Before returning `CONFORMANT`, it loads the registered ADL mission, rechecks
the current candidate and persisted handoff with canonical `teamctl`, and
requires every mapped check to be required by that work item and recorded as
PASS. A packet cannot define its own mandatory control set.

The result is read-only. It does not execute tests, persist a conformance
record, issue authorization, or activate a domain.

## Normalized evaluation packet

```json
{
  "domain_id": "example.domain",
  "candidate_id": "<64 lowercase hex characters>",
  "declared_result": "CONFORMANT",
  "open_critical_conflicts": [],
  "controls": [
    {"id": "scope", "result": "PASS", "evidence_refs": ["scope_check"]}
  ]
}
```

The separate `required_checks_by_control` argument is host-owned policy, for
example `{"scope": ["scope_check"]}`. The referenced checks must also be
declared required by the registered teamctl work item. Evidence references are
check IDs in the managed handoff, not arbitrary producer text or file paths.

## Verification basis and limits

The adapter reuses the existing `teamctl` identity, handoff, execution-receipt,
output, and log checks. It does not create another ledger or execution gateway.
The host-owned mapping determines which executed checks represent each domain
control. This adapter proves execution, receipt integrity and candidate
binding; it does not prove that a check's assertions are semantically adequate.

The reconstructed canonical files are
`docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json` and
`docs/domain-conformance/source/03_DOMAIN_CONFORMANCE_TEST_v1.0.md`. The schema
requires controls and evidence structure when `CONFORMANT` is declared; the
semantic verifier enforces exactly 13 mandatory control IDs, rejects duplicate
or non-PASS controls, and binds evidence refs to required managed checks.
Historical byte-for-byte compatibility with the absent source files remains
unverifiable. Activation/production integration remains `NOT_RUN`.

## Focused test

```text
python -m pytest tests/contracts/evidence/test_domain_conformance.py -q
```

Tests use isolated synthetic teamctl missions and child checks; they do not
contact model providers, network services, or production workspaces.
