# L8 · OpenMetadata Catalog Evidence

Generated: 2026-09-22 00:46:50 UTC

> Scope: deterministic fixture implementing the OpenMetadata-shaped client contract.
> No Docker container, OpenMetadata server, network call or production token was used.

## Acceptance checks

| Capability | Result | Evidence |
|---|---:|---|
| Catalog search | PASS | 2 matching entities for the Permit/evidence query |
| Source → asset → chunk lineage | PASS | 2 directional edges returned |
| Ownership assignment | PASS | `BAGO Data Governance` assigned to `asset-1` |
| Schema versioning | PASS | asset version updated to `2.0` |
| Quality rule | PASS | `content_hash_present` created as `quality-1` |
| Governance gate | PASS | all calls carried an ALLOW permit and receipt |

## Receipts

| Operation | Decision | Outcome | Results | Receipt |
|---|---|---:|---:|---|
| `search` | `ALLOW` | `SUCCESS` | 2 | `omreceipt_caa08a256e2d05b1` |
| `add_lineage` | `ALLOW` | `SUCCESS` | 1 | `omreceipt_2c7e571eff459585` |
| `add_lineage` | `ALLOW` | `SUCCESS` | 1 | `omreceipt_5f412401aaac86e6` |
| `get_lineage` | `ALLOW` | `SUCCESS` | 4 | `omreceipt_904de50aab7ec835` |
| `assign_ownership` | `ALLOW` | `SUCCESS` | 1 | `omreceipt_90e332b766ad53f0` |
| `register_schema_version` | `ALLOW` | `SUCCESS` | 1 | `omreceipt_fe3225582306c3c9` |
| `create_quality_rule` | `ALLOW` | `SUCCESS` | 1 | `omreceipt_d2f20752bbd6015b` |

## Boundary

This proves the BAGO adapter contract, request/permit enforcement, normalized
catalog entities, lineage and receipts. It does **not** prove a live
OpenMetadata deployment. Docker/OpenMetadata validation remains `NOT_RUN` in
this environment because `docker` and `docker compose` are unavailable.
