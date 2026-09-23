# L12 · Local Observability and Evals

Generated at: `2026-09-23T02:41:17.302856+00:00`

This zero-cost evidence composes the existing governed agent and local sandbox
receipts into one ordered trace, then evaluates the governance links locally:

```text
agent run
  → workflow stages
  → retrieval + citations
  → tool proposal + permit
  → execution result
  → sandbox execution
  → receipt + evidence reference
  → deterministic eval
```

## Boundary

- Cost: `0.0 USD`
- Trace storage: local in-memory object serialized as JSON; no collector or SaaS
- Model: injected Bedrock-shaped fixture; AWS live: `NOT_RUN`
- Sandbox: `LocalRestrictedBackend` with typed pytest request
- OpenMetadata remote: `NOT_RUN`

## Trace

- Trace: `trace-cddfe1dc5c7c6cc4`
- Agent run: `agent_run_443b2d3f91f62e72`
- Events: `13`
- Evidence references: `5`

| Seq | Event | Kind | Status | Parent | Evidence |
|---:|---|---|---|---|---|
| 0 | `agent.run` | `workflow` | `COMPLETED` | `—` | — |
| 1 | `classify_intent` | `workflow` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 2 | `retrieve_context` | `retrieval` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 3 | `reason_and_propose` | `workflow` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 4 | `authorize` | `authorization` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 5 | `execute` | `execution` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 6 | `verify_and_respond` | `workflow` | `SUCCESS` | `event-a231f8a2ef9e544a` | — |
| 7 | `retrieval` | `retrieval` | `SUCCESS` | `event-3cdf6aa4096a42b0` | docs/observability.md#revision=l12-v1, evidence/l12-observability.md#revision=l12-v1 |
| 8 | `tool_call` | `tool` | `SUCCESS` | `event-a4ae947bfd5fb0a9` | receipt://bedrock_receipt_320c74d8c047c8d9 |
| 9 | `permit` | `authorization` | `ALLOW` | `event-a989f4e920bc954e` | receipt://bedrock_receipt_320c74d8c047c8d9 |
| 10 | `receipt` | `receipt` | `SUCCESS` | `event-a989f4e920bc954e` | bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d |
| 11 | `sandbox_execution` | `sandbox` | `DENIED` | `event-a231f8a2ef9e544a` | sandbox://sbxreceipt-c97f8052daaa44ce |
| 12 | `receipt` | `receipt` | `DENIED` | `event-930e6dc45275e963` | sandbox://sbxreceipt-c97f8052daaa44ce |

## Evaluation

- Evaluation: `eval-c249ee760336307a`
- Status: `PASS`
- Score: `1.00`

| Check | Status | Detail |
|---|---|---|
| `trace_root` | PASS | agent.run root is present |
| `workflow_coverage` | PASS | all governed workflow stages are present |
| `retrieval_evidence` | PASS | retrieval hits are linked to citations |
| `permit_linkage` | PASS | tool requests retain authorization linkage |
| `receipt_linkage` | PASS | executions and receipts are linked to evidence |
| `no_unauthorized_effect` | PASS | denied or pending tools have no material call |
| `sandbox_receipt` | PASS | sandbox execution is linked to a receipt |

The evaluator checks trace root and workflow coverage, retrieval citations,
permit linkage, receipt linkage, absence of unauthorized effects and sandbox
receipt linkage. It does not judge LLM answer quality or claim production
observability infrastructure.

## Reproduce

```bash
python -m pytest tests/test_l12_observability.py -q
python scripts/run_l12_observability_evidence.py
```

## Full receipt

```json
{
  "aws_live": "NOT_RUN",
  "collector": "NOT_USED; local JSON trace only",
  "cost_usd": 0.0,
  "evaluation": {
    "checks": [
      {
        "detail": "agent.run root is present",
        "evidence_refs": [
          "docs/observability.md#revision=l12-v1",
          "evidence/l12-observability.md#revision=l12-v1",
          "receipt://bedrock_receipt_320c74d8c047c8d9",
          "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d",
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "name": "trace_root",
        "passed": true
      },
      {
        "detail": "all governed workflow stages are present",
        "evidence_refs": [
          "docs/observability.md#revision=l12-v1",
          "evidence/l12-observability.md#revision=l12-v1",
          "receipt://bedrock_receipt_320c74d8c047c8d9",
          "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d",
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "name": "workflow_coverage",
        "passed": true
      },
      {
        "detail": "retrieval hits are linked to citations",
        "evidence_refs": [
          "docs/observability.md#revision=l12-v1",
          "evidence/l12-observability.md#revision=l12-v1"
        ],
        "name": "retrieval_evidence",
        "passed": true
      },
      {
        "detail": "tool requests retain authorization linkage",
        "evidence_refs": [
          "receipt://bedrock_receipt_320c74d8c047c8d9"
        ],
        "name": "permit_linkage",
        "passed": true
      },
      {
        "detail": "executions and receipts are linked to evidence",
        "evidence_refs": [
          "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d",
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "name": "receipt_linkage",
        "passed": true
      },
      {
        "detail": "denied or pending tools have no material call",
        "evidence_refs": [
          "receipt://bedrock_receipt_320c74d8c047c8d9"
        ],
        "name": "no_unauthorized_effect",
        "passed": true
      },
      {
        "detail": "sandbox execution is linked to a receipt",
        "evidence_refs": [
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "name": "sandbox_receipt",
        "passed": true
      }
    ],
    "cost_usd": 0.0,
    "evaluation_id": "eval-c249ee760336307a",
    "evidence_refs": [
      "docs/observability.md#revision=l12-v1",
      "evidence/l12-observability.md#revision=l12-v1",
      "receipt://bedrock_receipt_320c74d8c047c8d9",
      "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d",
      "sandbox://sbxreceipt-c97f8052daaa44ce"
    ],
    "score": 1.0,
    "status": "PASS",
    "trace_id": "trace-cddfe1dc5c7c6cc4"
  },
  "fixtures": {
    "agent": {
      "answer": "Fixture L12 answer\n\nEvidence:\n- docs/observability.md#revision=l12-v1\n- evidence/l12-observability.md#revision=l12-v1",
      "citations": [
        "docs/observability.md#revision=l12-v1",
        "evidence/l12-observability.md#revision=l12-v1"
      ],
      "decision_receipts": [],
      "errors": [],
      "intent": "retrieval",
      "mcp_receipts": [],
      "ontology": null,
      "proposals": [
        {
          "arguments": {
            "inference_config": {
              "maxTokens": 384,
              "temperature": 0.0
            },
            "messages": [
              {
                "content": [
                  {
                    "text": "Question: ¿Qué evidencia valida la política de permisos?\n\nGoverned context:\n[1] La evidencia local valida la política de permisos gobernados.\nEvidence: docs/observability.md#revision=l12-v1\n\n[2] El receipt enlaza la decisión, el permiso y el efecto real.\nEvidence: evidence/l12-observability.md#revision=l12-v1\n\n\nReturn a concise answer with no unsupported claims."
                  }
                ],
                "role": "user"
              }
            ],
            "model_id": "fixture.l12-model",
            "system": [
              {
                "text": "Answer only from the governed context. Do not execute proposed tools."
              }
            ],
            "tool_config": {
              "tools": [
                {
                  "toolSpec": {
                    "description": "Propose an action for BAGO authorization; never execute it directly.",
                    "inputSchema": {
                      "json": {
                        "properties": {
                          "reason": {
                            "type": "string"
                          },
                          "tool_name": {
                            "type": "string"
                          }
                        },
                        "required": [
                          "tool_name",
                          "reason"
                        ],
                        "type": "object"
                      }
                    },
                    "name": "propose_governed_action"
                  }
                }
              ]
            }
          },
          "called": true,
          "context_revision": "l12-local-v1",
          "decision": "ALLOW",
          "effect_type": "EXTERNAL_API",
          "error_message": null,
          "outcome": "SUCCESS",
          "permit_id": "bedrock_permit_3b0641a55733993d",
          "proposal_id": "proposal_5f86c200a1d093f4",
          "rationale": "Provider generation is a separately governed external call.",
          "receipt_id": "bedrock_receipt_320c74d8c047c8d9",
          "request_id": "bedrock_req_86f8d276d43f147d",
          "result": "Fixture L12 answer",
          "tool_name": "bedrock.converse",
          "transport": "bedrock"
        }
      ],
      "provider_receipt": {
        "actual_effect": {
          "attempts": 1,
          "called": true,
          "model_id": "fixture.l12-model",
          "operation": "converse",
          "provider": "aws.bedrock"
        },
        "attempts": 1,
        "cost_usd": 0.0,
        "decision": "ALLOW",
        "duration_ms": 0,
        "error_kind": null,
        "error_message": null,
        "evidence_refs": [
          "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d"
        ],
        "execution_outcome": "SUCCESS",
        "model_id": "fixture.l12-model",
        "operation": "converse",
        "permit_id": "bedrock_permit_3b0641a55733993d",
        "receipt_id": "bedrock_receipt_320c74d8c047c8d9",
        "request_id": "bedrock_req_86f8d276d43f147d",
        "usage": {
          "input_tokens": 12,
          "output_tokens": 4,
          "total_tokens": 16
        }
      },
      "provider_text": "Fixture L12 answer",
      "query": "¿Qué evidencia valida la política de permisos?",
      "retrieval": {
        "citations": [
          "docs/observability.md#revision=l12-v1",
          "evidence/l12-observability.md#revision=l12-v1"
        ],
        "eligible_count": 2,
        "filtered_count": 0,
        "hits": [
          {
            "chunk_id": "l12-policy-chunk",
            "document_id": "l12-policy",
            "evidence": {
              "chunk_id": "l12-policy-chunk",
              "citation": "docs/observability.md#revision=l12-v1",
              "document_id": "l12-policy",
              "revision": "l12-v1",
              "source_uri": "docs/observability.md"
            },
            "lexical_score": 2.77258872,
            "rank": 1,
            "score": 1.13983095,
            "semantic_score": 0.64726017
          },
          {
            "chunk_id": "l12-receipt-chunk",
            "document_id": "l12-receipt",
            "evidence": {
              "chunk_id": "l12-receipt-chunk",
              "citation": "evidence/l12-observability.md#revision=l12-v1",
              "document_id": "l12-receipt",
              "revision": "l12-v1",
              "source_uri": "evidence/l12-observability.md"
            },
            "lexical_score": 0.0,
            "rank": 2,
            "score": 0.0016129,
            "semantic_score": 0.11519347
          }
        ],
        "intent": "retrieval",
        "metadata_filter": {
          "allowed_domains": [],
          "created_after": null,
          "include_superseded": false,
          "minimum_authority": "PROPOSED",
          "require_provenance": true,
          "required_classifications": []
        },
        "mode": "hybrid",
        "pipeline": [
          "intent_classification",
          "metadata_filters",
          "lexical_bm25",
          "semantic_embedding",
          "hybrid_rrf_fusion",
          "deterministic_reranker",
          "authority_validity_gate",
          "evidence_context_ready"
        ],
        "query": "¿Qué evidencia valida la política de permisos?",
        "reranked": true
      },
      "run_id": "agent_run_443b2d3f91f62e72",
      "status": "COMPLETED",
      "trace": [
        "classify_intent=retrieval; entities=none",
        "retrieve_context=hits:2; filtered:0",
        "reason_and_propose=proposals:1",
        "authorize=bedrock.converse:ALLOW:permit=bedrock_permit_3b0641a55733993d",
        "execute=bedrock.converse:SUCCESS",
        "verify_and_respond=status:COMPLETED; citations:2"
      ]
    },
    "bedrock_fixture_calls": 1,
    "sandbox": {
      "receipt": {
        "argv": [],
        "capability": "run_tests",
        "duration_ms": 0,
        "error_code": "PERMIT_NOT_ALLOWED",
        "error_message": "permit decision is not ALLOW",
        "evidence_refs": [
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "exit_code": null,
        "filesystem_mode": "unknown",
        "network_mode": "deny",
        "operation": "run_tests",
        "permit_id": "l12-sandbox-permit",
        "profile": "unknown",
        "receipt_id": "sbxreceipt-c97f8052daaa44ce",
        "request_id": "l12-sandbox-request",
        "sandbox_id": "",
        "status": "DENIED",
        "stderr_bytes": 0,
        "stderr_sha256": null,
        "stdout_bytes": 0,
        "stdout_sha256": null,
        "timed_out": false
      },
      "stderr": "",
      "stdout": "",
      "value": null
    }
  },
  "generated_at": "2026-09-23T02:41:17.302856+00:00",
  "openmetadata_remote": "NOT_RUN",
  "scope": "local-agent-trace-sandbox-receipt-evaluation",
  "trace": {
    "cost_usd": 0.0,
    "event_count": 13,
    "events": [
      {
        "attributes": {
          "intent": "retrieval",
          "query_sha256": "63d409411828dba40d0c85707a211002788c03c6394fcf4b93004ee3089c8166",
          "run_id": "agent_run_443b2d3f91f62e72"
        },
        "event_id": "event-a231f8a2ef9e544a",
        "evidence_refs": [],
        "kind": "workflow",
        "name": "agent.run",
        "parent_event_id": null,
        "sequence": 0,
        "status": "COMPLETED",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "retrieval; entities=none",
          "raw": "classify_intent=retrieval; entities=none"
        },
        "event_id": "event-d06379d938e2b733",
        "evidence_refs": [],
        "kind": "workflow",
        "name": "classify_intent",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 1,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "hits:2; filtered:0",
          "raw": "retrieve_context=hits:2; filtered:0"
        },
        "event_id": "event-3cdf6aa4096a42b0",
        "evidence_refs": [],
        "kind": "retrieval",
        "name": "retrieve_context",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 2,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "proposals:1",
          "raw": "reason_and_propose=proposals:1"
        },
        "event_id": "event-a4ae947bfd5fb0a9",
        "evidence_refs": [],
        "kind": "workflow",
        "name": "reason_and_propose",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 3,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "bedrock.converse:ALLOW:permit=bedrock_permit_3b0641a55733993d",
          "raw": "authorize=bedrock.converse:ALLOW:permit=bedrock_permit_3b0641a55733993d"
        },
        "event_id": "event-ddb02c9ab95f5e8b",
        "evidence_refs": [],
        "kind": "authorization",
        "name": "authorize",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 4,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "bedrock.converse:SUCCESS",
          "raw": "execute=bedrock.converse:SUCCESS"
        },
        "event_id": "event-dff6ebce7c449fa7",
        "evidence_refs": [],
        "kind": "execution",
        "name": "execute",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 5,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "detail": "status:COMPLETED; citations:2",
          "raw": "verify_and_respond=status:COMPLETED; citations:2"
        },
        "event_id": "event-97b9eb4944fce862",
        "evidence_refs": [],
        "kind": "workflow",
        "name": "verify_and_respond",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 6,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "eligible_count": 2,
          "filtered_count": 0,
          "hits": 2,
          "mode": "hybrid",
          "pipeline": [
            "intent_classification",
            "metadata_filters",
            "lexical_bm25",
            "semantic_embedding",
            "hybrid_rrf_fusion",
            "deterministic_reranker",
            "authority_validity_gate",
            "evidence_context_ready"
          ]
        },
        "event_id": "event-4621192e34670ff2",
        "evidence_refs": [
          "docs/observability.md#revision=l12-v1",
          "evidence/l12-observability.md#revision=l12-v1"
        ],
        "kind": "retrieval",
        "name": "retrieval",
        "parent_event_id": "event-3cdf6aa4096a42b0",
        "sequence": 7,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "called": true,
          "decision": "ALLOW",
          "effect_type": "EXTERNAL_API",
          "outcome": "SUCCESS",
          "permit_id": "bedrock_permit_3b0641a55733993d",
          "proposal_id": "proposal_5f86c200a1d093f4",
          "receipt_id": "bedrock_receipt_320c74d8c047c8d9",
          "request_id": "bedrock_req_86f8d276d43f147d",
          "tool_name": "bedrock.converse",
          "transport": "bedrock"
        },
        "event_id": "event-a989f4e920bc954e",
        "evidence_refs": [
          "receipt://bedrock_receipt_320c74d8c047c8d9"
        ],
        "kind": "tool",
        "name": "tool_call",
        "parent_event_id": "event-a4ae947bfd5fb0a9",
        "sequence": 8,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "decision": "ALLOW",
          "permit_id": "bedrock_permit_3b0641a55733993d",
          "request_id": "bedrock_req_86f8d276d43f147d",
          "tool_name": "bedrock.converse"
        },
        "event_id": "event-c54786970d5653eb",
        "evidence_refs": [
          "receipt://bedrock_receipt_320c74d8c047c8d9"
        ],
        "kind": "authorization",
        "name": "permit",
        "parent_event_id": "event-a989f4e920bc954e",
        "sequence": 9,
        "status": "ALLOW",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "called": true,
          "cost_usd": 0.0,
          "permit_id": "bedrock_permit_3b0641a55733993d",
          "receipt_id": "bedrock_receipt_320c74d8c047c8d9",
          "request_id": "bedrock_req_86f8d276d43f147d",
          "source": "provider"
        },
        "event_id": "event-c5aefa255ecab01a",
        "evidence_refs": [
          "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d"
        ],
        "kind": "receipt",
        "name": "receipt",
        "parent_event_id": "event-a989f4e920bc954e",
        "sequence": 10,
        "status": "SUCCESS",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "capability": "run_tests",
          "network_mode": "deny",
          "operation": "run_tests",
          "permit_id": "l12-sandbox-permit",
          "profile": "unknown",
          "receipt_id": "sbxreceipt-c97f8052daaa44ce",
          "request_id": "l12-sandbox-request"
        },
        "event_id": "event-930e6dc45275e963",
        "evidence_refs": [
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "kind": "sandbox",
        "name": "sandbox_execution",
        "parent_event_id": "event-a231f8a2ef9e544a",
        "sequence": 11,
        "status": "DENIED",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      },
      {
        "attributes": {
          "called": null,
          "cost_usd": 0.0,
          "permit_id": "l12-sandbox-permit",
          "receipt_id": "sbxreceipt-c97f8052daaa44ce",
          "request_id": "l12-sandbox-request",
          "source": "sandbox"
        },
        "event_id": "event-1ea05a100dce4dec",
        "evidence_refs": [
          "sandbox://sbxreceipt-c97f8052daaa44ce"
        ],
        "kind": "receipt",
        "name": "receipt",
        "parent_event_id": "event-930e6dc45275e963",
        "sequence": 12,
        "status": "DENIED",
        "trace_id": "trace-cddfe1dc5c7c6cc4"
      }
    ],
    "evidence_refs": [
      "docs/observability.md#revision=l12-v1",
      "evidence/l12-observability.md#revision=l12-v1",
      "receipt://bedrock_receipt_320c74d8c047c8d9",
      "bedrock://eu-west-1/fixture.l12-model/converse#request=bedrock_req_86f8d276d43f147d",
      "sandbox://sbxreceipt-c97f8052daaa44ce"
    ],
    "run_id": "agent_run_443b2d3f91f62e72",
    "trace_id": "trace-cddfe1dc5c7c6cc4"
  }
}
```
