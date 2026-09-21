"""Run the local MCP server through the BAGO governance adapter."""

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
EVIDENCE_PATH = REPO_ROOT / "evidence" / "mcp_governed_demo.md"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.mcp_adapter import GovernedMCPAdapter  # noqa: E402
from orchestration.state_graph import EffectType  # noqa: E402


async def run_demo() -> dict[str, Any]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            adapter = GovernedMCPAdapter("bago-local-demo")
            descriptors = adapter.discover_tools(listed.tools)
            adapter.register_tool(
                "get_lab_status",
                effect_type=EffectType.READ,
                approved_by="l5-demo-policy",
            )
            adapter.register_tool(
                "propose_lab_note",
                effect_type=EffectType.WRITE,
                approved_by="l5-demo-policy",
            )

            read_request = adapter.build_execution_request(
                "get_lab_status",
                {},
                proposed_by="l5-demo-agent",
                context_revision="l5-demo-v1",
            )
            read_permit = adapter.authorize(read_request)
            read_receipt = await adapter.call(session, read_request, read_permit)

            write_request = adapter.build_execution_request(
                "propose_lab_note",
                {"path": "notes/proposed.md", "content": "draft"},
                proposed_by="l5-demo-agent",
                context_revision="l5-demo-v1",
            )
            write_permit = adapter.authorize(write_request)
            write_receipt = await adapter.call(session, write_request, write_permit)

            return {
                "server": "bago-local-demo",
                "discovered": [descriptor.to_dict() for descriptor in descriptors],
                "registered": [
                    "get_lab_status:READ",
                    "propose_lab_note:WRITE",
                ],
                "read_call": read_receipt.to_dict(),
                "write_call": write_receipt.to_dict(),
            }


def render_evidence(result: dict[str, Any]) -> str:
    read_call = result["read_call"]
    write_call = result["write_call"]
    payload = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    return "\n".join(
        [
            "# L5 · Governed MCP local demo",
            "",
            f"Generated at: `{datetime.now(timezone.utc).isoformat()}`",
            "",
            "The demo starts `scripts/local_mcp_server.py` over MCP stdio, discovers",
            "two tools, explicitly registers their effect types in BAGO, and routes",
            "both calls through `GovernedMCPAdapter`.",
            "",
            f"- Discovered tools: `{len(result['discovered'])}`",
            f"- READ call: `{read_call['decision']}` / `{read_call['execution_outcome']}` / called=`{read_call['actual_effect']['called']}`",
            f"- WRITE call: `{write_call['decision']}` / called=`{write_call['actual_effect']['called']}`",
            "- The WRITE call is not sent to the MCP server because it requires explicit human authorization.",
            "",
            "## Receipt",
            "",
            "```json",
            payload,
            "```",
            "",
            "This is a local execution trace; the companion video is",
            "evidence/mcp_governed_demo.mp4 and its SHA-256 is recorded beside it.",
            "",
        ]
    )


def main() -> None:
    result = anyio.run(run_demo)
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
