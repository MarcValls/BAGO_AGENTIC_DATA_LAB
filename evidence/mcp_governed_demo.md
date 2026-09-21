# L5 · Governed MCP local demo

Generated at: `2026-09-21T23:38:20.752741+00:00`

The demo starts `scripts/local_mcp_server.py` over MCP stdio, discovers
two tools, explicitly registers their effect types in BAGO, and routes
both calls through `GovernedMCPAdapter`.

- Discovered tools: `2`
- READ call: `ALLOW` / `SUCCESS` / called=`True`
- WRITE call: `REQUIRE_HUMAN` / called=`False`
- The WRITE call is not sent to the MCP server because it requires explicit human authorization.

## Receipt

```json
{
  "discovered": [
    {
      "description": "Read-only status of the data lab",
      "fingerprint": "e8330c8afc3934b3",
      "input_schema": {
        "properties": {},
        "title": "get_lab_statusArguments",
        "type": "object"
      },
      "name": "get_lab_status",
      "output_schema": {
        "additionalProperties": {
          "type": "string"
        },
        "title": "get_lab_statusDictOutput",
        "type": "object"
      },
      "server_name": "bago-local-demo"
    },
    {
      "description": "Proposes a note change but is classified as a WRITE capability by BAGO",
      "fingerprint": "07068e5464d6e4dc",
      "input_schema": {
        "properties": {
          "content": {
            "title": "Content",
            "type": "string"
          },
          "path": {
            "title": "Path",
            "type": "string"
          }
        },
        "required": [
          "path",
          "content"
        ],
        "title": "propose_lab_noteArguments",
        "type": "object"
      },
      "name": "propose_lab_note",
      "output_schema": {
        "additionalProperties": {
          "type": "string"
        },
        "title": "propose_lab_noteDictOutput",
        "type": "object"
      },
      "server_name": "bago-local-demo"
    }
  ],
  "read_call": {
    "actual_effect": {
      "called": true,
      "server": "bago-local-demo",
      "tool": "get_lab_status"
    },
    "decision": "ALLOW",
    "duration_ms": 5,
    "error_message": null,
    "evidence_refs": [
      "mcp://bago-local-demo/tools/get_lab_status#request=mcp_req_2e821a9121284655"
    ],
    "execution_outcome": "SUCCESS",
    "permit_id": "mcp_permit_4032d7d85b00c502",
    "receipt_id": "mcp_receipt_7c35430aecaa4a8a",
    "request_id": "mcp_req_2e821a9121284655",
    "result": {
      "_meta": null,
      "content": [
        {
          "_meta": null,
          "annotations": null,
          "text": "{\n  \"project\": \"BAGO_AGENTIC_DATA_LAB\",\n  \"phase\": \"L5\",\n  \"status\": \"governed-mcp-demo\",\n  \"authority\": \"BAGO policy remains external to MCP\"\n}",
          "type": "text"
        }
      ],
      "isError": false,
      "structuredContent": {
        "authority": "BAGO policy remains external to MCP",
        "phase": "L5",
        "project": "BAGO_AGENTIC_DATA_LAB",
        "status": "governed-mcp-demo"
      }
    },
    "server_name": "bago-local-demo",
    "tool_name": "get_lab_status"
  },
  "registered": [
    "get_lab_status:READ",
    "propose_lab_note:WRITE"
  ],
  "server": "bago-local-demo",
  "write_call": {
    "actual_effect": {
      "called": false,
      "server": "bago-local-demo",
      "tool": "propose_lab_note"
    },
    "decision": "REQUIRE_HUMAN",
    "duration_ms": 0,
    "error_message": "DENY: permit decision is REQUIRE_HUMAN",
    "evidence_refs": [
      "mcp://bago-local-demo/tools/propose_lab_note#request=mcp_req_7444a9d8204b05c7"
    ],
    "execution_outcome": "FAILURE",
    "permit_id": "mcp_permit_7af549a46dc1e55b",
    "receipt_id": "mcp_receipt_f1d3e32c9192e5ef",
    "request_id": "mcp_req_7444a9d8204b05c7",
    "result": null,
    "server_name": "bago-local-demo",
    "tool_name": "propose_lab_note"
  }
}
```

This is a local execution trace; the companion video is
evidence/mcp_governed_demo.mp4 and its SHA-256 is recorded beside it.

Video SHA-256: `86c3eb75dee43569d02cd89178f89a80f223934dd2f16a29495b8e62796a81f8`
