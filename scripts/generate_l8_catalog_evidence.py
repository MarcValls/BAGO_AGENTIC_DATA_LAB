"""Generate a deterministic L8 catalog evidence artifact with an injected client."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters.openmetadata_adapter import (  # noqa: E402
    GovernedOpenMetadataAdapter,
    OpenMetadataCatalogPolicy,
    QualityRule,
)


class InMemoryOpenMetadataClient:
    """OpenMetadata-shaped fixture; it never opens a network connection."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {
            "source-1": {
                "id": "source-1",
                "type": "table",
                "fullyQualifiedName": "bago.source.documentation",
                "name": "documentation",
                "description": "BAGO source documents",
                "tags": [{"tagFQN": "BAGO.Source"}],
                "extension": {"bagoEntityType": "Source", "authority": "VERIFIED"},
            },
            "asset-1": {
                "id": "asset-1",
                "type": "table",
                "fullyQualifiedName": "bago.asset.execution_request_contract",
                "name": "execution_request_contract",
                "description": "ExecutionRequest Permit and evidence receipt contract",
                "tags": [{"tagFQN": "BAGO.Contract"}],
                "extension": {"bagoEntityType": "KnowledgeAsset", "authority": "VERIFIED"},
            },
            "chunk-1": {
                "id": "chunk-1",
                "type": "table",
                "fullyQualifiedName": "bago.chunk.execution_request_contract.000",
                "name": "execution_request_contract.000",
                "description": "Chunk with Permit and evidence receipt details",
                "tags": [{"tagFQN": "BAGO.KnowledgeChunk"}],
                "extension": {"bagoEntityType": "KnowledgeChunk", "authority": "VERIFIED"},
            },
        }
        self.edges: list[dict[str, Any]] = []
        self.quality_rules: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {"method": method, "path": path, "params": dict(params or {}), "json": json}
        )
        if method == "GET" and path == "/v1/search/query":
            query = str((params or {}).get("q", "")).lower()
            query_terms = [term for term in query.split() if term]
            matches = []
            for entity in self.entities.values():
                searchable = " ".join(
                    [
                        entity.get("name", ""),
                        entity.get("fullyQualifiedName", ""),
                        entity.get("description", ""),
                    ]
                ).lower()
                if all(term in searchable for term in query_terms):
                    matches.append({"_id": entity["id"], "_source": entity})
            return {"hits": {"hits": matches}}

        if method == "GET" and path.endswith("/lineage"):
            entity_id = path.split("/")[-2]
            upstream = [edge for edge in self.edges if edge["toEntity"] == entity_id]
            downstream = [edge for edge in self.edges if edge["fromEntity"] == entity_id]
            connected = {entity_id}
            for edge in upstream + downstream:
                connected.update({edge["fromEntity"], edge["toEntity"]})
            return {
                "nodes": [self.entities[item] for item in sorted(connected) if item != entity_id],
                "upstreamEdges": upstream,
                "downstreamEdges": downstream,
            }

        if method == "PUT" and path == "/v1/lineage":
            edge = dict((json or {}).get("edge", {}))
            source = edge.get("fromEntity", {})
            target = edge.get("toEntity", {})
            normalized = {
                "fromEntity": source.get("id", ""),
                "toEntity": target.get("id", ""),
                "lineageDetails": dict(edge.get("lineageDetails", {})),
            }
            if normalized not in self.edges:
                self.edges.append(normalized)
            return {"nodes": [], "downstreamEdges": [normalized]}

        if method == "PATCH" and "/v1/table/" in path:
            entity_id = path.rsplit("/", 1)[-1]
            entity = self.entities[entity_id]
            patch = dict(json or {})
            if "owners" in patch:
                entity["owners"] = patch["owners"]
            if "version" in patch:
                entity["version"] = patch["version"]
            if "schema" in patch:
                entity.setdefault("extension", {})["bagoSchema"] = patch["schema"]
            return {"entity": entity}

        if method == "POST" and path == "/v1/dataQuality/testDefinitions":
            rule = dict(json or {})
            rule["id"] = f"quality-{len(self.quality_rules) + 1}"
            self.quality_rules.append(rule)
            return rule

        raise AssertionError(f"fixture does not implement {method} {path}")


def _run() -> str:
    client = InMemoryOpenMetadataClient()
    adapter = GovernedOpenMetadataAdapter(
        policy=OpenMetadataCatalogPolicy(base_url="fixture://openmetadata/api"),
        client=client,
    )
    evidence_ref = "evidence/l8_openmetadata_catalog.md"
    receipts = []

    search_request = adapter.build_request(
        "search",
        proposed_by="l8-evidence-generator",
        context_revision="main@l7",
        resource="execution_request_contract",
        entity_type="table",
        query="Permit evidence receipt",
        evidence_refs=(evidence_ref,),
    )
    search_result = adapter.search(search_request, adapter.authorize(search_request))
    receipts.append(search_result.receipt)

    for source_id, target_id in (("source-1", "asset-1"), ("asset-1", "chunk-1")):
        lineage_request = adapter.build_request(
            "add_lineage",
            proposed_by="l8-evidence-generator",
            context_revision="main@l7",
            resource=target_id,
            entity_type="table",
            from_entity={"id": source_id, "type": "table"},
            to_entity={"id": target_id, "type": "table"},
            pipeline="bago-l2-etl",
            evidence_ref=evidence_ref,
            evidence_refs=(evidence_ref,),
        )
        lineage_result = adapter.add_lineage(lineage_request, adapter.authorize(lineage_request))
        receipts.append(lineage_result.receipt)

    graph_request = adapter.build_request(
        "get_lineage",
        proposed_by="l8-evidence-generator",
        context_revision="main@l7",
        resource="asset-1",
        entity_type="table",
        evidence_refs=(evidence_ref,),
    )
    graph_result = adapter.get_lineage(graph_request, adapter.authorize(graph_request))
    receipts.append(graph_result.receipt)

    owner_request = adapter.build_request(
        "assign_ownership",
        proposed_by="l8-evidence-generator",
        context_revision="main@l7",
        resource="asset-1",
        entity_type="table",
        owner_id="team-bago",
        owner_name="BAGO Data Governance",
        owner_type="team",
        evidence_refs=(evidence_ref,),
    )
    owner_result = adapter.assign_ownership(owner_request, adapter.authorize(owner_request))
    receipts.append(owner_result.receipt)

    version_request = adapter.build_request(
        "register_schema_version",
        proposed_by="l8-evidence-generator",
        context_revision="main@l7",
        resource="asset-1",
        entity_type="table",
        version="2.0",
        schema={"fields": ["content", "content_hash", "authority"]},
        evidence_refs=(evidence_ref,),
    )
    version_result = adapter.register_schema_version(version_request, adapter.authorize(version_request))
    receipts.append(version_result.receipt)

    rule_request = adapter.build_request(
        "create_quality_rule",
        proposed_by="l8-evidence-generator",
        context_revision="main@l7",
        quality_rule=QualityRule(
            name="content_hash_present",
            entity_fqn="bago.asset.execution_request_contract",
            severity="HIGH",
            parameters={"column": "content_hash"},
        ),
        evidence_refs=(evidence_ref,),
    )
    rule_result = adapter.create_quality_rule(rule_request, adapter.authorize(rule_request))
    receipts.append(rule_result.receipt)

    assert all(receipt.execution_outcome is not None for receipt in receipts)
    assert all(receipt.execution_outcome.value == "SUCCESS" for receipt in receipts)
    assert len(search_result.entities) == 2
    assert len(graph_result.lineage) == 2
    assert owner_result.entities[0].owner == "BAGO Data Governance"
    assert version_result.entities[0].version == "2.0"
    assert rule_result.raw_response["id"] == "quality-1"

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    receipt_rows = "\n".join(
        f"| `{receipt.operation}` | `{receipt.decision.value}` | `{receipt.execution_outcome.value}` | {receipt.result_count} | `{receipt.receipt_id}` |"
        for receipt in receipts
    )
    return f"""# L8 · OpenMetadata Catalog Evidence

Generated: {generated}

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
{receipt_rows}

## Boundary

This proves the BAGO adapter contract, request/permit enforcement, normalized
catalog entities, lineage and receipts. It does **not** prove a live
OpenMetadata deployment. Docker/OpenMetadata validation remains `NOT_RUN` in
this environment because `docker` and `docker compose` are unavailable.
"""


def main() -> None:
    output = REPO_ROOT / "evidence" / "l8_openmetadata_catalog.md"
    output.write_text(_run(), encoding="utf-8")
    print(output)
    print("fixture search=2 lineage_edges=2 ownership=PASS schema_version=2.0 quality_rule=PASS")


if __name__ == "__main__":
    main()
