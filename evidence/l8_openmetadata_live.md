# L8 · OpenMetadata local live evidence

Generated: 2026-09-23T01:16:43.363129+00:00

> Scope: real OpenMetadata server started locally with the pinned Docker Compose deployment.
> Temporary service, database, schema, tables and quality definition were created for the run.
> The script removes only those resource IDs after validation unless `--keep-data` is used.
> No AWS account, cloud credential or paid service was used.

- OpenMetadata image version: `1.12.6`
- Compose SHA256: `d19f9c1877368621452b626ae24e01722010d6fdcb0dc43b2b36bfc871f13f38`
- Adapter SHA256: `052e91cb9198def9d5f7fd1d8f15d0a44cfbfcc05728f436a84e0046d2d81c9d`
- Git HEAD observed: `4d1a3493ed29e381643085b140a739223aebe2da`
- Worktree dirty at execution: `True`
- Overall result: **PASS**

## Acceptance checks

| Check | Result | Detail |
|---|---:|---|
| server health | PASS | HTTP 200; server/database/deadlocks healthy |
| JWT authentication | PASS | local login returned a bearer token; token omitted from evidence |
| authenticated adapter search | PASS | 2 live entities |
| lineage write/read | PASS | 1 live edge(s) |
| ownership JSON Patch | PASS | table owner updated through /v1/tables |
| schema revision JSON Patch | PASS | native schemaDefinition updated |
| quality definition | PASS | real test definition created |
| pre-transport governance denial | PASS | REQUIRE_HUMAN stopped transport |

## Governed receipts

| Label | Decision | Outcome | Results | Path | Receipt |
|---|---|---|---:|---|---|
| search | ALLOW | SUCCESS | 2 | `/v1/search/query` | `omreceipt_6886d52553b0eb93` |
| add_lineage | ALLOW | SUCCESS | 0 | `/v1/lineage` | `omreceipt_0bf9ff4edbe085ff` |
| get_lineage | ALLOW | SUCCESS | 2 | `/v1/lineage/table/dc4b43ab-cb61-4500-9ed4-39c539873e8d` | `omreceipt_3c0ebb3cc8a4ce63` |
| assign_ownership | ALLOW | SUCCESS | 1 | `/v1/tables/dc4b43ab-cb61-4500-9ed4-39c539873e8d` | `omreceipt_d6bbdbd3a4b3fe4e` |
| register_schema_version | ALLOW | SUCCESS | 1 | `/v1/tables/dc4b43ab-cb61-4500-9ed4-39c539873e8d` | `omreceipt_a5783ce8b6068a0e` |
| create_quality_rule | ALLOW | SUCCESS | 1 | `/v1/dataQuality/testDefinitions` | `omreceipt_47abb603e79510af` |
| pre-transport denial | REQUIRE_HUMAN | FAILURE | 0 | `/v1/search/query` | `omreceipt_671d4bd4fb2b5d90` |

## Resource lifecycle

- Cleanup requested: `True`
- Cleanup result: `PASS`
- Resource names are run-scoped and are not treated as persistent project data.

## Boundary

This evidence proves the local Docker server, authenticated HTTP transport, real search, lineage write/read, table JSON Patch ownership/schema operations, quality-definition creation and pre-transport governance denial through the BAGO adapter. It does not prove AWS, a remote OpenMetadata deployment, OS-level sandbox isolation or production readiness.
