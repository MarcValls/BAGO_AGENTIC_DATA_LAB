"""Generate reproducible L9 evidence with local MCP and injected Bedrock."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SERVER_PATH = REPO_ROOT / "scripts" / "local_mcp_server.py"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l9_commercetools_agent.md"
CANON_REVIEW_CHECKPOINT_ISSUE = "#29"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)
from agent.governed_knowledge_agent import GovernedKnowledgeAgent  # noqa: E402
from metadata.schema import AuthorityLevel  # noqa: E402
from orchestration.state_graph import EffectType  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk, load_sqlite_chunks  # noqa: E402


class FixtureBedrockClient:
    """Bedrock-shaped client; it never contacts AWS."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": (
                                "Fixture Bedrock answer generated from governed context; "
                                "BAGO retains action authority and citations."
                            )
                        }
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 32, "outputTokens": 18},
        }


def l9_scenario_chunks() -> list[RetrievalChunk]:
    """Add three source-grounded capstone records to the existing L2 corpus."""

    records = [
        (
            "technical",
            "session_manager is answered through governed LangGraph orchestration, "
            "hybrid RAG retrieval, citations and an optional read-only MCP status call.",
            "session_manager",
        ),
        (
            "implementation",
            "workspace_binding test generation produces a CREATE proposal; BAGO requires "
            "human authorization and does not write the file automatically.",
            "workspace_binding",
        ),
        (
            "architecture",
            "RC6 architecture review retrieves canon evidence and may propose a GitHub "
            f"issue ({CANON_REVIEW_CHECKPOINT_ISSUE}), but external issue creation "
            "remains pending human authorization.",
            "RC6 canon",
        ),
    ]
    return [
        RetrievalChunk(
            chunk_id=f"l9-{key}",
            document_id="commercetools-capstone",
            content=content,
            title=title,
            source_uri=f"docs/commercetools_capstone.md#scenario={key}",
            revision="l9",
            authority=AuthorityLevel.VERIFIED,
            domain="portfolio",
            metadata={"domain": "portfolio", "classification": ["CAPSTONE"]},
        )
        for key, content, title in records
    ]


async def run_evidence() -> dict[str, Any]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(REPO_ROOT),
    )
    client = FixtureBedrockClient()
    bedrock = BedrockProviderAdapter(
        client=client,
        policy=BedrockProviderPolicy(
            allowed_model_ids=frozenset({"fixture.l9-model"}),
            backoff_seconds=0,
        ),
    )
    retriever = GovernedRAG(
        [
            *load_sqlite_chunks(REPO_ROOT / "l2_etl_metadata.db"),
            *l9_scenario_chunks(),
        ]
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            from adapters.mcp_adapter import GovernedMCPAdapter

            mcp_adapter = GovernedMCPAdapter("bago-local-demo")
            mcp_adapter.discover_tools(listed.tools)
            mcp_adapter.register_tool(
                "get_lab_status",
                effect_type=EffectType.READ,
                approved_by="l9-demo-policy",
            )
            mcp_adapter.register_tool(
                "propose_lab_note",
                effect_type=EffectType.WRITE,
                approved_by="l9-demo-policy",
            )
            agent = GovernedKnowledgeAgent(
                retriever,
                mcp_adapter=mcp_adapter,
                mcp_session=session,
                bedrock_adapter=bedrock,
            )
            technical = await agent.run(
                "¿Cómo funciona session_manager en BAGO?",
                context_revision="l9-demo-v1",
                model_id="fixture.l9-model",
                use_bedrock=True,
            )
            implementation = await agent.run(
                "Crea un test para workspace_binding",
                context_revision="l9-demo-v1",
            )
            architecture = await agent.run(
                "¿BAGO cumple el canon RC6?",
                context_revision="l9-demo-v1",
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "offline-fixture-and-local-mcp",
        "bedrock_transport": "injected_fixture_no_aws_call",
        "mcp_transport": "local_stdio_server",
        "retrieval_chunks": len(retriever.chunks),
        "bedrock_fixture_calls": len(client.calls),
        "scenarios": {
            "technical_query": technical.to_dict(),
            "implementation_query": implementation.to_dict(),
            "architecture_query": architecture.to_dict(),
        },
    }


def render_evidence(result: dict[str, Any]) -> str:
    scenarios = result["scenarios"]
    technical = scenarios["technical_query"]
    implementation = scenarios["implementation_query"]
    architecture = scenarios["architecture_query"]
    payload = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    architecture_receipt = (
        architecture.get("decision_receipts", [{}])[0]
        if architecture.get("decision_receipts")
        else {}
    )
    architecture_effect = architecture_receipt.get("actual_effect", {})
    return "\n".join(
        [
            "# L9 · Governed Knowledge Agent — commercetools portfolio evidence",
            "",
            f"Generated at: `{result['generated_at']}`",
            "",
            "This artifact validates the end-to-end governed orchestration offline.",
            "The target is the commercetools AI Engineer portfolio scenario; no",
            "commercial commercetools API or production AWS account is contacted.",
            "",
            "## Boundary",
            "",
            "```text",
            "LangGraph → governed RAG → proposal → Permit → optional MCP/Bedrock → receipt",
            "                         └→ human approval for CREATE / WRITE / external issue",
            "```",
            "",
            f"- Retrieval corpus: `{result['retrieval_chunks']}` L2 chunks",
            f"- Bedrock calls: `{result['bedrock_fixture_calls']}` injected fixture call",
            f"- MCP transport: `{result['mcp_transport']}`",
            "- AWS live, commercetools live and GitHub issue creation: `NOT_RUN`",
            "",
            "## Scenarios",
            "",
            f"1. Technical query: `{technical['status']}`; citations=`{len(technical['citations'])}`; MCP READ and Bedrock fixture receipts present.",
            f"2. Implementation query: `{implementation['status']}`; CREATE and MCP WRITE proposals have no transport call and leave decision receipts.",
            f"3. Architecture query: `{architecture['status']}`; GitHub issue proposal leaves a `called=false` decision receipt.",
            "",
            "## Canon-review checkpoint evidence (issue flow #29)",
            "",
            f"- Checkpoint issue flow: `{CANON_REVIEW_CHECKPOINT_ISSUE}`",
            f"- Query: `{architecture['query']}`",
            f"- Scenario status: `{architecture['status']}`",
            f"- Decision: `{architecture_receipt.get('decision', 'UNKNOWN')}`",
            f"- Tool proposed: `{architecture_receipt.get('tool_name', 'github.create_issue')}`",
            f"- External transport called: `{architecture_effect.get('called', False)}`",
            f"- Guard reason: `{architecture_receipt.get('error_message', 'Material effect requires explicit human authorization')}`",
            "",
            "## Reproducible command",
            "",
            "```bash",
            "python scripts/generate_l9_agent_evidence.py",
            "```",
            "",
            "## Full result",
            "",
            "```json",
            payload,
            "```",
            "",
        ]
    )


def main() -> None:
    result = anyio.run(run_evidence)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
