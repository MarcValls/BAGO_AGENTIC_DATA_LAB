# L8 · OpenMetadata local live evidence

Generated: 2026-09-23T22:15:16.015561+00:00

> Scope: real OpenMetadata server started locally with the pinned Docker Compose deployment.
> Temporary service, database, schema, tables and quality definition were created for the run.
> The script removes only those resource IDs after validation unless `--keep-data` is used.
> No AWS account, cloud credential or paid service was used.

- OpenMetadata image version: `1.12.6`
- Compose SHA256: `6b3b2f019e7f43e8a3db76689a52f883b944bb2ad4bac05bff8e2291900f033a`
- Adapter SHA256: `acc74428059eaf895cf6a91b539d8c725424d5bcde0110a2e48d9a5f652c32f5`
- Git HEAD observed: `1a1a0eed8d52dfdf43c1c2e42d40effe4e603e1b`
- Worktree dirty at execution: `False`
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
| search | ALLOW | SUCCESS | 2 | `/v1/search/query` | `omreceipt_84ba37d8dc4bc5d3` |
| add_lineage | ALLOW | SUCCESS | 0 | `/v1/lineage` | `omreceipt_5863e37a80332456` |
| get_lineage | ALLOW | SUCCESS | 2 | `/v1/lineage/table/b074ed2f-bf83-422f-be5a-3b729e34334e` | `omreceipt_c2201a799f9502b9` |
| assign_ownership | ALLOW | SUCCESS | 1 | `/v1/tables/b074ed2f-bf83-422f-be5a-3b729e34334e` | `omreceipt_a7a175fda2b83d9c` |
| register_schema_version | ALLOW | SUCCESS | 1 | `/v1/tables/b074ed2f-bf83-422f-be5a-3b729e34334e` | `omreceipt_064aad86ed4f7263` |
| create_quality_rule | ALLOW | SUCCESS | 1 | `/v1/dataQuality/testDefinitions` | `omreceipt_e716eb4965dcb6e7` |
| pre-transport denial | REQUIRE_HUMAN | FAILURE | 0 | `/v1/search/query` | `omreceipt_62f949e071387e5b` |

## Resource lifecycle

- Cleanup requested: `True`
- Cleanup result: `PASS`
- Resource names are run-scoped and are not treated as persistent project data.

## Boundary

This evidence proves the local Docker server, authenticated HTTP transport, real search, lineage write/read, table JSON Patch ownership/schema operations, quality-definition creation and pre-transport governance denial through the BAGO adapter. It does not prove AWS, a remote OpenMetadata deployment, OS-level sandbox isolation or production readiness.
