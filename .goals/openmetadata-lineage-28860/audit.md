# OpenMetadata #28860 — local reproduction and governed-adapter validation

**Audit date:** 2026-10-03
**Authorization:** Marc Valls explicitly authorized a disposable local OpenMetadata `1.12.10` run and a minimal adapter extension if evidence justified it.
**Frozen baseline:** `v1.0.0` / `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`
**Work branch:** `real-world/openmetadata-28860-v1.1`, created at the frozen commit; no v1.0 tag, artifact, or tracked release commit was changed.

## Verdict

**The core missing-dataset/no-lineage behavior was reproduced against the actual OpenLineage event API on OpenMetadata `1.12.10`.** The exact public issue request was not byte-for-byte reproducible from the issue body, and its title names a different route. In the observed event API response, HTTP 200 alone was not sufficient evidence of lineage: the body said `lineageEdgesCreated: 0` and `Event processed, no lineage edges created`. The absent table entities were independently confirmed by HTTP 404 reads.

The server attempted to auto-create tables when their schema existed, but the table insert failed with `SQLIntegrityConstraintViolationException: Column 'updatedAt' cannot be null`; with an absent schema, it logged that the schema could not be found. No tables or edges were persisted in either missing-dataset case. A positive control with pre-existing tables returned one edge, and a lineage read showed `source=OpenLineage`.

A minimal governed client operation was added on the post-v1.0 branch. It uses the correct OpenLineage endpoint and records a 2xx response with zero edges as `PARTIAL`, not `SUCCESS`. **No OpenMetadata server fix is included or claimed.**

## A1 — Issue and route identity

- Issue: https://github.com/open-metadata/OpenMetadata/issues/28860; state `OPEN`; title prefix `[Feature Request]`; GitHub returned no labels.
- The public body reports an HTTP 200 with dropped lineage and asks for stub creation when a dataset namespace can be associated with a registered service. It gives `1.12.10` as the tested version, but the retrieved body does not include a complete literal URL/FQN/request/response payload.
- The issue title says `/api/v1/lineage`. Version-matched OpenMetadata source and its SDK register the single-event API as **`POST /api/v1/openlineage/lineage`**. The generic `/api/v1/lineage` API is different: a local `POST` with an OpenLineage event returned `405`; `PUT` returned `400` because that API expects an `AddLineage` envelope, not a RunEvent.
- The 1.12.x connector documentation describes connector-side resolution behavior; it is not sufficient to infer the contract of the direct OpenLineage REST resource. This audit used the version-matched server source/runtime for the direct API.

## A2 — Exact local target and isolation

- OpenMetadata release tag: `1.12.10-release`, source commit `3bc20e698abf222742908c2aa5d0eaa736e7cfbd`.
- Official release Compose asset: `docker-compose.yml`; SHA-256 `8b5c23178803169e41c6c0a8ab1da6b0c65e8007c98a4a6d107a33f3074596d0`.
- Local image identities:
  - server `docker.getcollate.io/openmetadata/server:1.12.10` — `sha256:f2fb66b1ea6420a84c986e1035a55308948807352efe9d87ce510612d0dd404c`;
  - DB `docker.getcollate.io/openmetadata/db:1.12.10` — `sha256:3b8f467ff0b418cf3bedd30b1cc29a30f8c832376db0461acf5ab41ba516a8ed`;
  - Elasticsearch `9.3.0` — `sha256:4f6bdcb742e892539c6ac49b0dd3e4e182e90218546e8c6a22db378c344acb60`.
- Ran as isolated Compose project `bago-om28860-11210`, with separate project network/data and loopback-only host ports `18585`/`18586`. Used the official server and DB images; omitted the unrelated ingestion/Airflow container and disabled the server's pipeline client. Healthcheck returned HTTP 200 and healthy database/server state.
- The already-existing Data Lab OpenMetadata `1.12.6` containers were not modified. No remote OpenMetadata endpoint, AWS, or commercetools call was made. Temporary local scripts/Compose files were removed after the run; no credentials were retained in repository evidence.

## A3 — Runtime observations

A temporary database service, database, and schema were created. Events used `eventType=COMPLETE`, UUID run IDs, a namespace equal to the temporary registered service name, and dataset names scoped to that service/database/schema.

| Scenario | Event API result | Independent verification |
|---|---|---|
| Input/output tables absent; schema exists | `POST /api/v1/openlineage/lineage` → HTTP 200; JSON `status=success`, `lineageEdgesCreated=0`, message `Event processed, no lineage edges created` | Both table lookups returned 404; server log records attempted table creation failing on `updatedAt cannot be null`; no edge was created |
| Input/output tables and schema absent | HTTP 200; same zero-edge response | Both table lookups returned 404; server log says `Cannot create table, schema not found` |
| Positive control: source/target tables pre-created | HTTP 200; `lineageEdgesCreated=1` | Lineage GET by source table ID returned a downstream edge whose `lineageDetails.source` is `OpenLineage` |

The public issue's use of “silent” needs qualification: **the status code alone is non-diagnostic, but this 1.12.10 response body explicitly reports zero edges**. The table-creation SQL error is only in the server log. The runtime evidence reproduces the core no-stub/no-edge condition on the proper REST event route, not the issue's absent literal payload or its title's generic route. An initial direct lineage query used an FQN where the API expected an entity ID and returned HTTP 400; it is not counted as verification. The positive-control lineage read by table ID succeeded.

Version-matched source reviewed at the release commit:

- `openmetadata-service/.../resources/lineage/OpenLineageResource.java`: route registration, default OpenLineage settings, and response construction (`success` plus zero count when no edge is created).
- `openmetadata-service/.../openlineage/OpenLineageEntityResolver.java`: auto-create path requires a resolvable existing schema; the created table object does not populate the DB-required `updatedAt` field in the failing path.
- `openmetadata-service/.../openlineage/OpenLineageMapper.java`: unresolved inputs/outputs are skipped with a warning.
- `openmetadata-integration-tests/.../OpenLineageLineageResolutionIT.java`: positive existing-entity resolution tests, but not the observed database insert failure.

## A4 — Minimal BAGO adapter change

`src/adapters/openmetadata_adapter.py` now exposes `ingest_openlineage_event` as a `WRITE` operation through the existing `ExecutionRequest`/`Permit`/receipt boundary. It accepts one JSON-compatible `COMPLETE` event with a UUID run ID and non-empty input/output datasets; its request resource must match that run ID. It posts only to `/v1/openlineage/lineage` and validates the response status/count. A 2xx response with zero edges produces an `ExecutionOutcome.PARTIAL` receipt with `result_count=0` and the server message; a positive edge count produces `SUCCESS` with that count and no error message. This reports/observes upstream behavior; it does not synthesize entities or claim to fix OpenMetadata.

`tests/test_openmetadata_adapter.py` adds OpenLineage coverage for route/payload, positive and zero-edge outcomes, permit and event validation, response count validation, and failure/partial response handling.

## A5 — Verification and evidence

- Targeted adapter tests on Python 3.11.9: **27 passed**.
- Full suite on the CI version, Python 3.11.9, in a temporary venv populated from pinned `requirements.txt`: **162 passed**. The venv was removed after verification; no project dependency files changed.
- Full suite on available Python 3.14: **162 passed**, 5 compatibility/deprecation warnings. Python 3.11 `compileall` passed for changed files.
- Independent read-only review found no critical issue; confirmed frozen baseline, tracked scope, evidence hashes, and the archived-success-receipt caveat.
- Live governed-adapter positive control: receipt `SUCCESS`, `result_count=1`; independent lineage read contained the edge. The captured receipt predates final adapter hardening: its successful response stores the server message in `error_message`, while final code leaves that field empty on `SUCCESS` and tightens event/resource validation. The live HTTP result, edge count, persisted edge, and zero-edge `PARTIAL` behavior remain valid; final semantics are covered by unit tests.
- Live governed-adapter missing-entity case: receipt `PARTIAL`, `result_count=0`, response still HTTP 200; independent entity reads returned 404.
- A recursive hard-delete request returned HTTP 200 but its response included `deleted: false`; that response alone is not treated as proof. Follow-up service/database/schema/table reads each returned 404. The isolated Compose project, project network and named volume were then removed; temporary Compose files and scripts were deleted. The local Data Lab `1.12.6` containers were left untouched.
- Evidence files under `.goals/openmetadata-lineage-28860/evidence/` contain direct and adapter request/response/read-back records, follow-up cleanup lookups, and selected server log lines. They contain no bearer token or password. `SHA256SUMS.txt` provides checksums for the four JSON/log evidence files. SHA-256: direct JSON `d7021a950a1ce1fcbd7d0c245abdf54d38c03e4cbdffb7fb7073c8531960f06c`; governed JSON `b5992a76372ec29dce2461c43bb574ed0863d17142268209d190d86809622669`; server observations `8d4fb038d1dcae1cb001302efa194934ae9c3eef8f1129b2e642c0821f4ec625`; cleanup reads `bdbd7daea403eeb6f3ca8758cccd02073f7c0d40c014727e6c247a337fdcb2a5`.

## Findings

- **P0: 0.**
- **P1: 1.** On the tested `1.12.10` image, the direct OpenLineage API reports HTTP 200/success while creating zero lineage edges for missing datasets. With an existing schema, the auto-create insert fails because `updatedAt` is null; with a missing schema, creation is skipped. This is a reproduced server-side behavior on the correct event endpoint; upstream remediation is outside this BAGO change.
- **P2: 1.** The public issue's literal request/response is incomplete and its title route differs from the actual event route. Exact issue-level reproduction cannot be asserted; only the core missing-dataset behavior was reproduced with a controlled fixture.

## Cross-repository Layer discovery (read-only, separate from #28860)

The user's machine contains a promoted/frozen `LAYERED_ARTIFACT_ENGINE v0.9-FIX8` contract archive at:

`Documents/IA. LA PREGUNTA/E_KITS_Y_HERRAMIENTAS/BAGO/03_soft_layers/LAYERED_ARTIFACT_ENGINE_v0.9-FIX8_FROZEN.zip`

The archive records canonical contract SHA-256 `d15ecd534f6f6ee34daff78107886c6d695b84d4790c04fbb4a0c35c2bf6c65e`, `P0=0/P1=0`, and contract-semantic `LAE-01…24 = 24 PASS`. Its own freeze/retest records say **`FROZEN · NOT_IMPLEMENTED`** and distinguish contract-level validation from runnable runtime integration/production validation.

A separate BAGO repo (`C:/Users/AMTEC_Terminal_1º/BAGO`) contains a candidate MVP/CLI implementation (`backend/bago_core/layered_artifact_engine.py`, `backend/bago_core/commands/cmd_layer.py`, `backend/tests/test_layer_cli.py`). Its internal goal records report 8 isolated MVP unit tests and 2 focused CLI tests, while the CLI goal marks global validation `NOT_RUN`. These files are untracked in that repo's current branch and its working tree has extensive unrelated modifications. They are candidate material, not a clean canonical runtime dependency; no files were edited and no tests were executed there.

Do not claim that the frozen v0.9-FIX8 contract package contains an implemented reusable engine. Any Layer work remains separate.

## Freeze integrity and next gate

The work branch was created from exact frozen commit `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`. No tag, release asset, v1.0.0 source, Compose file, or other tracked v1.0 artifact was changed. Adapter/tests were committed as `14ab65f97fa90bc7d12387748ac98ff821f12654`; generated README metrics were refreshed in `85007a1da4871670e8aa06a661e3056652a776a0`. PR [#36](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/36) was pushed with passing full-suite and README checks; a live GitHub query now reports it merged at `c2a7768e15da59e57aae132c0aac492c63de5a64` on 2026-10-03 12:28:36Z, attributed to account `MarcValls`. The assistant did not execute the merge; explicit authorization had covered push and PR creation, not merge. The remote `v1.0.0` tag still peels to `b584235ecfdbc2ecb1c3d601ce40fb4f973ff2e8`. No release or external OpenMetadata issue activity occurred.

Before merging/releasing, decide separately whether to pursue upstream OpenMetadata remediation and obtain the exact request fixture from the issue author if exact endpoint reproduction is required. This BAGO change only makes submission governed and zero-edge outcomes visible.
