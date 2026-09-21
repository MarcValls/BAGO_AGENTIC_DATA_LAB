"""Small MCP stdio server used by the governed L5 demonstration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("BAGO Local MCP Demo")


@mcp.tool(name="get_lab_status", description="Read-only status of the data lab")
def get_lab_status() -> dict[str, str]:
    return {
        "project": "BAGO_AGENTIC_DATA_LAB",
        "phase": "L5",
        "status": "governed-mcp-demo",
        "authority": "BAGO policy remains external to MCP",
    }


@mcp.tool(
    name="propose_lab_note",
    description="Proposes a note change but is classified as a WRITE capability by BAGO",
)
def propose_lab_note(path: str, content: str) -> dict[str, str]:
    """Return a proposal only; the adapter must still gate this WRITE effect."""

    return {"status": "proposal-only", "path": path, "content": content}


if __name__ == "__main__":
    mcp.run(transport="stdio")
