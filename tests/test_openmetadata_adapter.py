"""CRIT P0 tests for the governed OpenMetadata catalog adapter."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import adapters.openmetadata_adapter as openmetadata_module  # noqa: E402
from adapters.openmetadata_adapter import (  # noqa: E402
    GovernedOpenMetadataAdapter,
    OpenMetadataCatalogPolicy,
    OpenMetadataErrorKind,
    OpenMetadataHTTPError,
    QualityRule,
)


class FakeCatalogClient:
    def __init__(self, responses=None, errors=None):
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls = []

    def request(self, method, path, *, params=None, json=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": dict(params or {}),
                "json": json,
                "timeout": timeout,
            }
        )
        if self.errors:
            error = self.errors.pop(0)
            raise error
        return self.responses.pop(0) if self.responses else {}


def make_request(adapter, operation, **kwargs):
    request = adapter.build_request(
        operation,
        proposed_by="l8-test-agent",
        context_revision="main@l7",
        **kwargs,
    )
    return request, adapter.authorize(request)


def test_request_and_permit_are_scoped_to_openmetadata_operation():
    adapter = GovernedOpenMetadataAdapter(
        policy=OpenMetadataCatalogPolicy(base_url="http://catalog.test/api")
    )

    request, permit = make_request(
        adapter,
        "search",
        resource="Permit",
        entity_type="table",
        query="Permit",
    )

    assert request.tool_name == "openmetadata.search"
    assert request.effect_type.value == "READ"
    assert permit.decision.value == "ALLOW"
    assert "operation=search" in permit.constraints
    assert permit.signed_by == "bago.openmetadata.policy"


def test_missing_permit_never_calls_catalog_transport():
    client = FakeCatalogClient(
        responses=[{"hits": {"hits": []}}]
    )
    adapter = GovernedOpenMetadataAdapter(client=client)
    request, _ = make_request(
        adapter,
        "search",
        resource="Permit",
        entity_type="table",
        query="Permit",
    )

    result = adapter.search(request, None)

    assert client.calls == []
    assert result.receipt.decision.value == "DENY"
    assert result.receipt.error_kind is OpenMetadataErrorKind.AUTHORIZATION


def test_entity_allowlist_rejects_out_of_scope_requests_before_transport():
    adapter = GovernedOpenMetadataAdapter(
        policy=OpenMetadataCatalogPolicy(allowed_entity_types=frozenset({"table"}))
    )

    with pytest.raises(ValueError, match="outside policy"):
        make_request(
            adapter,
            "search",
            resource="Dashboard",
            entity_type="dashboard",
            query="Dashboard",
        )


def test_search_normalizes_hits_and_preserves_metadata_filter_shape():
    client = FakeCatalogClient(
        responses=[
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "asset-1",
                            "_source": {
                                "id": "asset-1",
                                "type": "table",
                                "fullyQualifiedName": "bago.contract",
                                "name": "contract",
                                "description": "Execution contract",
                                "owners": [{"name": "BAGO", "type": "team"}],
                                "tags": [{"tagFQN": "BAGO.Contract"}],
                                "version": 1.2,
                                "extension": {"authority": "VERIFIED"},
                            },
                        }
                    ]
                }
            }
        ]
    )
    adapter = GovernedOpenMetadataAdapter(client=client)
    request, permit = make_request(
        adapter,
        "search",
        resource="bago.contract",
        entity_type="table",
        query="execution contract",
        offset=10,
        page_size=5,
    )

    result = adapter.search(request, permit)

    assert result.entities[0].fully_qualified_name == "bago.contract"
    assert result.entities[0].owner == "BAGO"
    assert result.entities[0].tags == ("BAGO.Contract",)
    assert result.entities[0].authority == "VERIFIED"
    assert client.calls[0]["path"] == "/v1/search/query"
    assert client.calls[0]["params"]["q"] == "execution contract"
    assert client.calls[0]["params"]["from"] == 10
    assert client.calls[0]["params"]["size"] == 5


def test_lineage_normalization_returns_nodes_and_directional_edges():
    client = FakeCatalogClient(
        responses=[
            {
                "nodes": [
                    {
                        "id": "chunk-1",
                        "type": "table",
                        "fullyQualifiedName": "bago.chunk.1",
                        "name": "chunk.1",
                    }
                ],
                "upstreamEdges": [
                    {
                        "fromEntity": "source-1",
                        "toEntity": "asset-1",
                        "lineageDetails": {"evidenceRef": "evidence/l8.md"},
                    }
                ],
                "downstreamEdges": [
                    {
                        "fromEntity": "asset-1",
                        "toEntity": "chunk-1",
                        "lineageDetails": {"pipeline": {"name": "etl"}},
                    }
                ],
            }
        ]
    )
    adapter = GovernedOpenMetadataAdapter(client=client)
    request, permit = make_request(
        adapter,
        "get_lineage",
        resource="asset-1",
        entity_type="table",
        upstream_depth=2,
        downstream_depth=3,
    )

    result = adapter.get_lineage(request, permit)

    assert len(result.entities) == 1
    assert len(result.lineage) == 2
    assert result.lineage[0].evidence_ref == "evidence/l8.md"
    assert result.lineage[1].pipeline == "etl"
    assert client.calls[0]["path"] == "/v1/lineage/table/asset-1"
    assert client.calls[0]["params"] == {"upstreamDepth": 2, "downstreamDepth": 3}


def test_add_lineage_builds_openmetadata_edge_and_receipt():
    client = FakeCatalogClient(
        responses=[
            {
                "nodes": [],
                "downstreamEdges": [
                    {
                        "fromEntity": "source-1",
                        "toEntity": "asset-1",
                        "lineageDetails": {"evidenceRef": "evidence/l8.md"},
                    }
                ],
            }
        ]
    )
    adapter = GovernedOpenMetadataAdapter(client=client)
    request, permit = make_request(
        adapter,
        "add_lineage",
        resource="asset-1",
        entity_type="table",
        from_entity={"id": "source-1", "type": "table"},
        to_entity={"id": "asset-1", "type": "table"},
        evidence_ref="evidence/l8.md",
    )

    result = adapter.add_lineage(request, permit)

    body = client.calls[0]["json"]
    assert body["edge"]["fromEntity"]["id"] == "source-1"
    assert body["edge"]["toEntity"]["id"] == "asset-1"
    assert body["edge"]["lineageDetails"]["evidenceRef"] == "evidence/l8.md"
    assert result.receipt.execution_outcome.value == "SUCCESS"
    assert result.receipt.actual_effect["method"] == "PUT"


def test_ownership_schema_version_and_quality_rule_use_write_permits():
    client = FakeCatalogClient(
        responses=[
            {"entity": {"id": "asset-1", "type": "table", "name": "contract"}},
            {"entity": {"id": "asset-1", "type": "table", "version": "2.0"}},
            {"id": "rule-1", "name": "content_hash_present", "type": "testDefinition"},
        ]
    )
    adapter = GovernedOpenMetadataAdapter(client=client)

    owner_request, owner_permit = make_request(
        adapter,
        "assign_ownership",
        resource="asset-1",
        entity_type="table",
        owner_id="team-1",
        owner_name="BAGO Data Governance",
        owner_type="team",
    )
    version_request, version_permit = make_request(
        adapter,
        "register_schema_version",
        resource="asset-1",
        entity_type="table",
        version="2.0",
        schema={"fields": ["content", "content_hash"]},
    )
    quality_request, quality_permit = make_request(
        adapter,
        "create_quality_rule",
        quality_rule=QualityRule(
            name="content_hash_present",
            entity_fqn="bago.contract",
            severity="HIGH",
            parameters={"column": "content_hash"},
        ),
    )

    adapter.assign_ownership(owner_request, owner_permit)
    adapter.register_schema_version(version_request, version_permit)
    quality_result = adapter.create_quality_rule(quality_request, quality_permit)

    assert [call["method"] for call in client.calls] == ["PATCH", "PATCH", "POST"]
    assert client.calls[0]["path"] == "/v1/tables/asset-1"
    assert client.calls[0]["json"][0]["value"][0]["name"] == "BAGO Data Governance"
    assert client.calls[1]["path"] == "/v1/tables/asset-1"
    assert '"version":"2.0"' in client.calls[1]["json"][0]["value"]
    assert client.calls[2]["json"]["entityType"] == "TABLE"
    assert quality_result.receipt.operation == "create_quality_rule"


def test_throttle_retries_are_bounded():
    sleeps = []
    client = FakeCatalogClient(
        responses=[{"data": []}],
        errors=[OpenMetadataHTTPError(429, "throttled"), OpenMetadataHTTPError(429, "throttled")],
    )
    adapter = GovernedOpenMetadataAdapter(
        client=client,
        policy=OpenMetadataCatalogPolicy(max_attempts=3, backoff_seconds=0.01),
        sleep_fn=sleeps.append,
    )
    request, permit = make_request(
        adapter,
        "search",
        resource="contract",
        entity_type="table",
        query="contract",
    )

    result = adapter.search(request, permit)

    assert result.receipt.execution_outcome.value == "SUCCESS"
    assert result.receipt.attempts == 3
    assert len(client.calls) == 3
    assert sleeps == [0.01, 0.02]


def test_authorization_error_does_not_retry():
    client = FakeCatalogClient(errors=[OpenMetadataHTTPError(403, "forbidden")])
    adapter = GovernedOpenMetadataAdapter(
        client=client,
        policy=OpenMetadataCatalogPolicy(max_attempts=5),
    )
    request, permit = make_request(
        adapter,
        "search",
        resource="contract",
        entity_type="table",
        query="contract",
    )

    result = adapter.search(request, permit)

    assert result.receipt.error_kind is OpenMetadataErrorKind.AUTHORIZATION
    assert result.receipt.attempts == 1
    assert len(client.calls) == 1


def test_local_rate_limit_blocks_second_call_before_transport():
    client = FakeCatalogClient(responses=[{"data": []}])
    adapter = GovernedOpenMetadataAdapter(
        client=client,
        policy=OpenMetadataCatalogPolicy(max_calls_per_window=1),
    )
    first_request, first_permit = make_request(
        adapter,
        "search",
        resource="one",
        entity_type="table",
        query="one",
    )
    second_request, second_permit = make_request(
        adapter,
        "search",
        resource="two",
        entity_type="table",
        query="two",
    )

    first = adapter.search(first_request, first_permit)
    second = adapter.search(second_request, second_permit)

    assert first.receipt.execution_outcome.value == "SUCCESS"
    assert second.receipt.error_kind is OpenMetadataErrorKind.RATE_LIMIT
    assert len(client.calls) == 1


def test_quality_rule_rejects_invalid_entity_type_and_severity():
    with pytest.raises(ValueError, match="entity_type"):
        QualityRule(name="rule", entity_fqn="asset", entity_type="DOCUMENT")
    with pytest.raises(ValueError, match="severity"):
        QualityRule(name="rule", entity_fqn="asset", severity="UNKNOWN")


def test_receipt_is_serializable_and_classification_is_stable():
    client = FakeCatalogClient(responses=[{"data": []}])
    adapter = GovernedOpenMetadataAdapter(client=client)
    request, permit = make_request(
        adapter,
        "search",
        resource="contract",
        entity_type="table",
        query="contract",
    )

    result = adapter.search(request, permit)
    receipt = result.receipt.to_dict()

    assert receipt["receipt_id"].startswith("omreceipt_")
    assert receipt["actual_effect"]["path"] == "/v1/search/query"
    assert GovernedOpenMetadataAdapter.classify_error(OpenMetadataHTTPError(404)) is OpenMetadataErrorKind.NOT_FOUND


def test_stdlib_client_sends_optional_bearer_token_without_exposing_it_in_policy_repr(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(openmetadata_module, "urlopen", fake_urlopen)
    policy = OpenMetadataCatalogPolicy(
        base_url="http://catalog.test/api",
        auth_token="local-token",
        timeout_seconds=7,
    )

    openmetadata_module._StdlibOpenMetadataClient(policy).request(
        "GET", "/v1/search/query", params={"q": "contract"}
    )

    assert captured["headers"]["Authorization"] == "Bearer local-token"
    assert captured["timeout"] == 7
    assert "local-token" not in repr(policy)
