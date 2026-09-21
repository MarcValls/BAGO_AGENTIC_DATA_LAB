"""L5 MCP governance tests, including a real local stdio round trip."""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from adapters.mcp_adapter import (  # noqa: E402
    GovernedMCPAdapter,
    MCPGovernanceError,
)
from orchestration.state_graph import (  # noqa: E402
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
)
from run_mcp_demo import run_demo  # noqa: E402


def _tool(name: str, schema: dict | None = None) -> dict:
    return {
        "name": name,
        "description": f"test tool {name}",
        "inputSchema": schema or {"type": "object", "properties": {}},
    }


def _adapter() -> GovernedMCPAdapter:
    adapter = GovernedMCPAdapter("test-server")
    adapter.discover_tools([_tool("read_status"), _tool("write_note")])
    return adapter


def test_discovery_is_not_registration_or_authority():
    adapter = _adapter()

    assert [item.name for item in adapter.registry.discovered] == [
        "read_status",
        "write_note",
    ]
    assert adapter.registry.registered == ()
    with pytest.raises(MCPGovernanceError, match="not registered"):
        adapter.build_execution_request(
            "read_status",
            {},
            proposed_by="agent",
            context_revision="ctx-v1",
        )


def test_registration_explicitly_classifies_effect_and_preserves_schema():
    adapter = GovernedMCPAdapter("test-server")
    adapter.discover_tools(
        [
            _tool(
                "read_status",
                {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                    "additionalProperties": False,
                },
            )
        ]
    )
    registration = adapter.register_tool(
        "read_status",
        effect_type=EffectType.READ,
        approved_by="test-policy",
    )
    request = adapter.build_execution_request(
        "read_status",
        {"detail": "full"},
        proposed_by="agent",
        context_revision="ctx-v1",
    )

    assert registration.effect_type is EffectType.READ
    assert request.effect_type is EffectType.READ
    assert request.parameters == {"detail": "full"}


def test_schema_validation_blocks_missing_and_unknown_arguments():
    adapter = GovernedMCPAdapter("test-server")
    adapter.discover_tools(
        [
            _tool(
                "read_status",
                {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                    "additionalProperties": False,
                },
            )
        ]
    )
    adapter.register_tool(
        "read_status",
        effect_type=EffectType.READ,
        approved_by="test-policy",
    )

    with pytest.raises(MCPGovernanceError, match="Missing required"):
        adapter.build_execution_request(
            "read_status", {}, proposed_by="agent", context_revision="ctx-v1"
        )
    with pytest.raises(MCPGovernanceError, match="Unknown MCP arguments"):
        adapter.build_execution_request(
            "read_status",
            {"detail": "full", "unexpected": True},
            proposed_by="agent",
            context_revision="ctx-v1",
        )


def test_read_is_auto_allowed_with_scoped_permit():
    adapter = _adapter()
    adapter.register_tool(
        "read_status",
        effect_type=EffectType.READ,
        approved_by="test-policy",
    )
    request = adapter.build_execution_request(
        "read_status", {}, proposed_by="agent", context_revision="ctx-v1"
    )
    permit = adapter.authorize(request)

    assert permit.decision is AuthorizationDecision.ALLOW
    assert permit.request_id == request.request_id
    assert "registered_capability" in permit.constraints


def test_write_requires_human_and_denied_call_never_reaches_session():
    adapter = _adapter()
    adapter.register_tool(
        "write_note",
        effect_type=EffectType.WRITE,
        approved_by="test-policy",
    )
    request = adapter.build_execution_request(
        "write_note", {}, proposed_by="agent", context_revision="ctx-v1"
    )
    permit = adapter.authorize(request)
    calls: list[str] = []

    class Session:
        async def call_tool(self, **kwargs):
            calls.append(kwargs["name"])
            raise AssertionError("denied MCP call reached the server")

    receipt = anyio.run(adapter.call, Session(), request, permit)

    assert permit.decision is AuthorizationDecision.REQUIRE_HUMAN
    assert receipt.decision is AuthorizationDecision.REQUIRE_HUMAN
    assert receipt.execution_outcome is ExecutionOutcome.FAILURE
    assert receipt.actual_effect["called"] is False
    assert calls == []


def test_mismatched_permit_is_denied_without_transport_call():
    adapter = _adapter()
    adapter.register_tool(
        "read_status",
        effect_type=EffectType.READ,
        approved_by="test-policy",
    )
    request = adapter.build_execution_request(
        "read_status", {}, proposed_by="agent", context_revision="ctx-v1"
    )
    other_request = adapter.build_execution_request(
        "read_status", {}, proposed_by="other-agent", context_revision="ctx-v2"
    )
    permit = adapter.authorize(other_request)

    class Session:
        async def call_tool(self, **kwargs):
            raise AssertionError("mismatched permit reached the server")

    receipt = anyio.run(adapter.call, Session(), request, permit)

    assert receipt.decision is AuthorizationDecision.DENY
    assert receipt.actual_effect["called"] is False
    assert "different request" in (receipt.error_message or "")


def test_local_mcp_server_round_trip_is_governed():
    result = anyio.run(run_demo)

    assert {item["name"] for item in result["discovered"]} == {
        "get_lab_status",
        "propose_lab_note",
    }
    assert result["read_call"]["decision"] == "ALLOW"
    assert result["read_call"]["execution_outcome"] == "SUCCESS"
    assert result["read_call"]["actual_effect"]["called"] is True
    assert result["write_call"]["decision"] == "REQUIRE_HUMAN"
    assert result["write_call"]["actual_effect"]["called"] is False
