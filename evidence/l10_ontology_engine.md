# L10 · Governed Ontology Engine — local RDF/SPARQL evidence

Generated at: `2026-09-22T12:46:23.247901+00:00`

This receipt demonstrates the first L10 case over a deterministic local graph:

```text
RAG retrieves governed chunks
  → ontology engine resolves RDF relations
  → inverse/transitive inference materializes paths
  → constraints flag contradictions and missing evidence
  → path + evidence + receipt are passed to the LLM context
```

## Boundary

- Cost: `0.0 USD`
- RDF store: local in-memory graph; no Docker or paid service
- SPARQL: bounded local `SELECT` subset (triple joins, `FILTER regex`/equality, `LIMIT`)
- LLM: injected Bedrock-shaped fixture; AWS call: `NOT_RUN`
- OpenMetadata live: `NOT_RUN`
- Fixture received ontology context: `True`

## Query and receipt

Question: `¿Qué sustituye a la política anterior y qué evidencia la valida?`

- Receipt: `ontology_receipt_e29c0d506f581e1b`
- Outcome: `CONSTRAINT_VIOLATION`
- Explicit triples: `41`
- Inferred triples: `3`
- Paths found: `4`
- Contradictions found: `1`
- Evidence refs: `3`

The `CONSTRAINT_VIOLATION` outcome is intentional: the fixture contains an
explicit contradictory candidate so the engine demonstrates detection instead
of silently producing a green answer.

## RDF/Turtle materialization

```turtle
@prefix bago: <https://bago.local/ontology/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://bago.local/ontology/candidate_policy> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .
<https://bago.local/ontology/candidate_policy> <http://www.w3.org/2000/01/rdf-schema#label> "Candidate policy" .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/authority> "PROPOSED" .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/contradicts> <https://bago.local/ontology/policy_v2> .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/description> "An incompatible experimental policy" .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/provenance> "docs/candidate-policy.md" .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/validity> "CURRENT" .
<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/version> "0.1.0" .
<https://bago.local/ontology/policy_receipt> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/EVIDENCE> .
<https://bago.local/ontology/policy_receipt> <http://www.w3.org/2000/01/rdf-schema#label> "Policy v2 validation receipt" .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/authority> "VERIFIED" .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/description> "Evidence validating the current policy" .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/provenance> "evidence/policy-receipt.md" .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/source> <https://bago.local/ontology/source_evidence> .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/validates> <https://bago.local/ontology/policy_v2> .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/validity> "CURRENT" .
<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/version> "1.0.0" .
<https://bago.local/ontology/policy_v1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .
<https://bago.local/ontology/policy_v1> <http://www.w3.org/2000/01/rdf-schema#label> "Permit policy v1" .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/authority> "CANONICAL" .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/description> "Previous permit policy" .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/provenance> "docs/policy-v1.md" .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/supersededBy> <https://bago.local/ontology/policy_v2> .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/validity> "SUPERSEDED" .
<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/version> "1.0.0" .
<https://bago.local/ontology/policy_v2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .
<https://bago.local/ontology/policy_v2> <http://www.w3.org/2000/01/rdf-schema#label> "Permit policy v2" .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/authority> "VERIFIED" .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/contradicts> <https://bago.local/ontology/candidate_policy> .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/description> "Current governed permit policy" .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/provenance> "docs/policy-v2.md" .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/supersedes> <https://bago.local/ontology/policy_v1> .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/validatedBy> <https://bago.local/ontology/policy_receipt> .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/validity> "CURRENT" .
<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/version> "2.0.0" .
<https://bago.local/ontology/source_evidence> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/Source> .
<https://bago.local/ontology/source_evidence> <http://www.w3.org/2000/01/rdf-schema#label> "evidence/policy-receipt.md" .
<https://bago.local/ontology/source_evidence> <https://bago.local/ontology/uri> "evidence/policy-receipt.md" .
<https://bago.local/ontology/source_policy> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/Source> .
<https://bago.local/ontology/source_policy> <http://www.w3.org/2000/01/rdf-schema#label> "docs/policy.md" .
<https://bago.local/ontology/source_policy> <https://bago.local/ontology/uri> "docs/policy.md" .

```

## Reasoning result

```text
Ontology Engine (RDF/SPARQL local, coste=0):
Paths:
- policy_v2 -[supersedes]-> policy_v1
- policy_v2 -[validatedBy]-> policy_receipt [inferred]
- policy_receipt -[validates]-> policy_v2
- policy_receipt -[validates]-> policy_v2 -[supersedes]-> policy_v1
Inferences: 1 derived triples materialized locally.
Contradictions: 1 explicit conflict relation(s) detected.
Evidence: docs/policy-v1.md#revision=1.0.0, docs/policy-v2.md#revision=2.0.0, evidence/policy-receipt.md#revision=1.0.0
Receipt: ontology_receipt_e29c0d506f581e1b outcome=CONSTRAINT_VIOLATION triples=44
```

## Reproduce

```bash
python -m pytest tests/test_l10_ontology_engine.py -q
python scripts/generate_l10_ontology_evidence.py
```

## Full receipt

```json
{
  "agent": {
    "answer": "Fixture LLM reasoned over the governed RDF path; BAGO retains evidence and contradiction authority.\n\nEvidence:\n- docs/policy-v2.md#revision=2.0.0\n- evidence/policy-receipt.md#revision=1.0.0\n- docs/policy-v1.md#revision=1.0.0",
    "citations": [
      "docs/policy-v2.md#revision=2.0.0",
      "evidence/policy-receipt.md#revision=1.0.0",
      "docs/policy-v1.md#revision=1.0.0"
    ],
    "decision_receipts": [],
    "errors": [],
    "intent": "retrieval",
    "mcp_receipts": [],
    "ontology": {
      "evidence_refs": [
        "docs/policy-v1.md#revision=1.0.0",
        "docs/policy-v2.md#revision=2.0.0",
        "evidence/policy-receipt.md#revision=1.0.0"
      ],
      "inferred_triples": [
        {
          "evidence_refs": [
            "docs/policy-v2.md#revision=2.0.0",
            "evidence/policy-receipt.md#revision=1.0.0"
          ],
          "inference_rule": "inverse:validates",
          "inferred": true,
          "object": "https://bago.local/ontology/policy_receipt",
          "object_is_literal": false,
          "predicate": "https://bago.local/ontology/validatedBy",
          "subject": "https://bago.local/ontology/policy_v2"
        }
      ],
      "paths": [
        {
          "evidence_refs": [
            "docs/policy-v1.md#revision=1.0.0",
            "docs/policy-v2.md#revision=2.0.0"
          ],
          "nodes": [
            "https://bago.local/ontology/policy_v2",
            "https://bago.local/ontology/policy_v1"
          ],
          "triples": [
            {
              "evidence_refs": [
                "docs/policy-v1.md#revision=1.0.0",
                "docs/policy-v2.md#revision=2.0.0"
              ],
              "inference_rule": "",
              "inferred": false,
              "object": "https://bago.local/ontology/policy_v1",
              "object_is_literal": false,
              "predicate": "https://bago.local/ontology/supersedes",
              "subject": "https://bago.local/ontology/policy_v2"
            }
          ]
        },
        {
          "evidence_refs": [
            "docs/policy-v2.md#revision=2.0.0",
            "evidence/policy-receipt.md#revision=1.0.0"
          ],
          "nodes": [
            "https://bago.local/ontology/policy_v2",
            "https://bago.local/ontology/policy_receipt"
          ],
          "triples": [
            {
              "evidence_refs": [
                "docs/policy-v2.md#revision=2.0.0",
                "evidence/policy-receipt.md#revision=1.0.0"
              ],
              "inference_rule": "inverse:validates",
              "inferred": true,
              "object": "https://bago.local/ontology/policy_receipt",
              "object_is_literal": false,
              "predicate": "https://bago.local/ontology/validatedBy",
              "subject": "https://bago.local/ontology/policy_v2"
            }
          ]
        },
        {
          "evidence_refs": [
            "docs/policy-v2.md#revision=2.0.0",
            "evidence/policy-receipt.md#revision=1.0.0"
          ],
          "nodes": [
            "https://bago.local/ontology/policy_receipt",
            "https://bago.local/ontology/policy_v2"
          ],
          "triples": [
            {
              "evidence_refs": [
                "docs/policy-v2.md#revision=2.0.0",
                "evidence/policy-receipt.md#revision=1.0.0"
              ],
              "inference_rule": "",
              "inferred": false,
              "object": "https://bago.local/ontology/policy_v2",
              "object_is_literal": false,
              "predicate": "https://bago.local/ontology/validates",
              "subject": "https://bago.local/ontology/policy_receipt"
            }
          ]
        },
        {
          "evidence_refs": [
            "docs/policy-v1.md#revision=1.0.0",
            "docs/policy-v2.md#revision=2.0.0",
            "evidence/policy-receipt.md#revision=1.0.0"
          ],
          "nodes": [
            "https://bago.local/ontology/policy_receipt",
            "https://bago.local/ontology/policy_v2",
            "https://bago.local/ontology/policy_v1"
          ],
          "triples": [
            {
              "evidence_refs": [
                "docs/policy-v2.md#revision=2.0.0",
                "evidence/policy-receipt.md#revision=1.0.0"
              ],
              "inference_rule": "",
              "inferred": false,
              "object": "https://bago.local/ontology/policy_v2",
              "object_is_literal": false,
              "predicate": "https://bago.local/ontology/validates",
              "subject": "https://bago.local/ontology/policy_receipt"
            },
            {
              "evidence_refs": [
                "docs/policy-v1.md#revision=1.0.0",
                "docs/policy-v2.md#revision=2.0.0"
              ],
              "inference_rule": "",
              "inferred": false,
              "object": "https://bago.local/ontology/policy_v1",
              "object_is_literal": false,
              "predicate": "https://bago.local/ontology/supersedes",
              "subject": "https://bago.local/ontology/policy_v2"
            }
          ]
        }
      ],
      "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
      "receipt": {
        "constraints_checked": 1,
        "contradictions_found": 1,
        "cost_usd": 0.0,
        "evidence_refs": [
          "docs/policy-v1.md#revision=1.0.0",
          "docs/policy-v2.md#revision=2.0.0",
          "evidence/policy-receipt.md#revision=1.0.0"
        ],
        "explicit_triples": 41,
        "graph_fingerprint": "744acafe44e20ddb83950b85434000b4d95fda4d56b79d7efc0a923cb7184135",
        "inferred_triples": 3,
        "outcome": "CONSTRAINT_VIOLATION",
        "paths_found": 4,
        "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
        "receipt_id": "ontology_receipt_e29c0d506f581e1b",
        "sparql_queries": [
          "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:supersedes ?object . } LIMIT 50",
          "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:validates ?object . } LIMIT 50",
          "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:validatedBy ?object . } LIMIT 50"
        ]
      },
      "sparql_bindings": [
        {
          "object": "https://bago.local/ontology/policy_v1",
          "subject": "https://bago.local/ontology/policy_v2"
        },
        {
          "object": "https://bago.local/ontology/policy_v2",
          "subject": "https://bago.local/ontology/policy_receipt"
        },
        {
          "object": "https://bago.local/ontology/policy_receipt",
          "subject": "https://bago.local/ontology/policy_v2"
        }
      ],
      "summary": "Ontology Engine (RDF/SPARQL local, coste=0):\nPaths:\n- policy_v2 -[supersedes]-> policy_v1\n- policy_v2 -[validatedBy]-> policy_receipt [inferred]\n- policy_receipt -[validates]-> policy_v2\n- policy_receipt -[validates]-> policy_v2 -[supersedes]-> policy_v1\nInferences: 1 derived triples materialized locally.\nContradictions: 1 explicit conflict relation(s) detected.\nEvidence: docs/policy-v1.md#revision=1.0.0, docs/policy-v2.md#revision=2.0.0, evidence/policy-receipt.md#revision=1.0.0\nReceipt: ontology_receipt_e29c0d506f581e1b outcome=CONSTRAINT_VIOLATION triples=44",
      "violations": [
        {
          "code": "CONTRADICTION",
          "evidence_refs": [
            "docs/candidate-policy.md#revision=0.1.0",
            "docs/policy-v2.md#revision=2.0.0"
          ],
          "message": "Contradictory relation detected between https://bago.local/ontology/candidate_policy and https://bago.local/ontology/policy_v2",
          "severity": "ERROR"
        }
      ]
    },
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
                  "text": "Question: ¿Qué sustituye a la política anterior y qué evidencia la valida?\n\nGoverned context:\n[1] La política de permisos v2 sustituye la política v1; una evidencia verifica y valida la política vigente.\nEvidence: docs/policy-v2.md#revision=2.0.0\n\n[2] La evidencia policy receipt valida la política de permisos v2.\nEvidence: evidence/policy-receipt.md#revision=1.0.0\n\nOntology Engine (RDF/SPARQL local, coste=0):\nPaths:\n- policy_v2 -[supersedes]-> policy_v1\n- policy_v2 -[validatedBy]-> policy_receipt [inferred]\n- policy_receipt -[validates]-> policy_v2\n- policy_receipt -[validates]-> policy_v2 -[supersedes]-> policy_v1\nInferences: 1 derived triples materialized locally.\nContradictions: 1 explicit conflict relation(s) detected.\nEvidence: docs/policy-v1.md#revision=1.0.0, docs/policy-v2.md#revision=2.0.0, evidence/policy-receipt.md#revision=1.0.0\nReceipt: ontology_receipt_e29c0d506f581e1b outcome=CONSTRAINT_VIOLATION triples=44\n\nReturn a concise answer with no unsupported claims."
                }
              ],
              "role": "user"
            }
          ],
          "model_id": "fixture.l10-model",
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
        "context_revision": "l10-local-v1",
        "decision": "ALLOW",
        "effect_type": "EXTERNAL_API",
        "error_message": null,
        "outcome": "SUCCESS",
        "permit_id": "bedrock_permit_7aa1a357602f3ec5",
        "proposal_id": "proposal_55b4bebeab70e635",
        "rationale": "Provider generation is a separately governed external call.",
        "receipt_id": "bedrock_receipt_184a0992391f9857",
        "request_id": "bedrock_req_4a55b3d3fc600969",
        "result": "Fixture LLM reasoned over the governed RDF path; BAGO retains evidence and contradiction authority.",
        "tool_name": "bedrock.converse",
        "transport": "bedrock"
      }
    ],
    "provider_receipt": {
      "actual_effect": {
        "attempts": 1,
        "called": true,
        "model_id": "fixture.l10-model",
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
        "bedrock://eu-west-1/fixture.l10-model/converse#request=bedrock_req_4a55b3d3fc600969"
      ],
      "execution_outcome": "SUCCESS",
      "model_id": "fixture.l10-model",
      "operation": "converse",
      "permit_id": "bedrock_permit_7aa1a357602f3ec5",
      "receipt_id": "bedrock_receipt_184a0992391f9857",
      "request_id": "bedrock_req_4a55b3d3fc600969",
      "usage": {
        "input_tokens": 64,
        "output_tokens": 18,
        "total_tokens": 82
      }
    },
    "provider_text": "Fixture LLM reasoned over the governed RDF path; BAGO retains evidence and contradiction authority.",
    "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
    "retrieval": {
      "citations": [
        "docs/policy-v2.md#revision=2.0.0",
        "evidence/policy-receipt.md#revision=1.0.0"
      ],
      "eligible_count": 2,
      "filtered_count": 0,
      "hits": [
        {
          "chunk_id": "policy-v2-chunk",
          "document_id": "policy_v2",
          "evidence": {
            "chunk_id": "policy-v2-chunk",
            "citation": "docs/policy-v2.md#revision=2.0.0",
            "document_id": "policy_v2",
            "revision": "2.0.0",
            "source_uri": "docs/policy-v2.md"
          },
          "lexical_score": 1.24950368,
          "rank": 1,
          "score": 1.10829424,
          "semantic_score": 0.66530739
        },
        {
          "chunk_id": "policy-receipt-chunk",
          "document_id": "policy_receipt",
          "evidence": {
            "chunk_id": "policy-receipt-chunk",
            "citation": "evidence/policy-receipt.md#revision=1.0.0",
            "document_id": "policy_receipt",
            "revision": "1.0.0",
            "source_uri": "evidence/policy-receipt.md"
          },
          "lexical_score": 0.60773852,
          "rank": 2,
          "score": 0.0769739,
          "semantic_score": 0.53797683
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
      "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
      "reranked": true
    },
    "run_id": "agent_run_30fe70eef1f8f33e",
    "status": "CONSTRAINT_VIOLATION",
    "trace": [
      "classify_intent=retrieval; entities=none",
      "retrieve_context=hits:2; filtered:0",
      "ontology_engine=paths:4;inferred:1;contradictions:1;receipt:ontology_receipt_e29c0d506f581e1b",
      "reason_and_propose=proposals:1",
      "authorize=bedrock.converse:ALLOW:permit=bedrock_permit_7aa1a357602f3ec5",
      "execute=bedrock.converse:SUCCESS",
      "verify_and_respond=status:CONSTRAINT_VIOLATION; citations:3"
    ]
  },
  "aws_live": "NOT_RUN",
  "cost_usd": 0.0,
  "generated_at": "2026-09-22T12:46:23.247901+00:00",
  "llm_fixture": {
    "calls": 1,
    "prompt_contains_ontology_engine": true,
    "transport": "injected_fixture_no_aws_call"
  },
  "ontology": {
    "evidence_refs": [
      "docs/policy-v1.md#revision=1.0.0",
      "docs/policy-v2.md#revision=2.0.0",
      "evidence/policy-receipt.md#revision=1.0.0"
    ],
    "inferred_triples": [
      {
        "evidence_refs": [
          "docs/policy-v2.md#revision=2.0.0",
          "evidence/policy-receipt.md#revision=1.0.0"
        ],
        "inference_rule": "inverse:validates",
        "inferred": true,
        "object": "https://bago.local/ontology/policy_receipt",
        "object_is_literal": false,
        "predicate": "https://bago.local/ontology/validatedBy",
        "subject": "https://bago.local/ontology/policy_v2"
      }
    ],
    "paths": [
      {
        "evidence_refs": [
          "docs/policy-v1.md#revision=1.0.0",
          "docs/policy-v2.md#revision=2.0.0"
        ],
        "nodes": [
          "https://bago.local/ontology/policy_v2",
          "https://bago.local/ontology/policy_v1"
        ],
        "triples": [
          {
            "evidence_refs": [
              "docs/policy-v1.md#revision=1.0.0",
              "docs/policy-v2.md#revision=2.0.0"
            ],
            "inference_rule": "",
            "inferred": false,
            "object": "https://bago.local/ontology/policy_v1",
            "object_is_literal": false,
            "predicate": "https://bago.local/ontology/supersedes",
            "subject": "https://bago.local/ontology/policy_v2"
          }
        ]
      },
      {
        "evidence_refs": [
          "docs/policy-v2.md#revision=2.0.0",
          "evidence/policy-receipt.md#revision=1.0.0"
        ],
        "nodes": [
          "https://bago.local/ontology/policy_v2",
          "https://bago.local/ontology/policy_receipt"
        ],
        "triples": [
          {
            "evidence_refs": [
              "docs/policy-v2.md#revision=2.0.0",
              "evidence/policy-receipt.md#revision=1.0.0"
            ],
            "inference_rule": "inverse:validates",
            "inferred": true,
            "object": "https://bago.local/ontology/policy_receipt",
            "object_is_literal": false,
            "predicate": "https://bago.local/ontology/validatedBy",
            "subject": "https://bago.local/ontology/policy_v2"
          }
        ]
      },
      {
        "evidence_refs": [
          "docs/policy-v2.md#revision=2.0.0",
          "evidence/policy-receipt.md#revision=1.0.0"
        ],
        "nodes": [
          "https://bago.local/ontology/policy_receipt",
          "https://bago.local/ontology/policy_v2"
        ],
        "triples": [
          {
            "evidence_refs": [
              "docs/policy-v2.md#revision=2.0.0",
              "evidence/policy-receipt.md#revision=1.0.0"
            ],
            "inference_rule": "",
            "inferred": false,
            "object": "https://bago.local/ontology/policy_v2",
            "object_is_literal": false,
            "predicate": "https://bago.local/ontology/validates",
            "subject": "https://bago.local/ontology/policy_receipt"
          }
        ]
      },
      {
        "evidence_refs": [
          "docs/policy-v1.md#revision=1.0.0",
          "docs/policy-v2.md#revision=2.0.0",
          "evidence/policy-receipt.md#revision=1.0.0"
        ],
        "nodes": [
          "https://bago.local/ontology/policy_receipt",
          "https://bago.local/ontology/policy_v2",
          "https://bago.local/ontology/policy_v1"
        ],
        "triples": [
          {
            "evidence_refs": [
              "docs/policy-v2.md#revision=2.0.0",
              "evidence/policy-receipt.md#revision=1.0.0"
            ],
            "inference_rule": "",
            "inferred": false,
            "object": "https://bago.local/ontology/policy_v2",
            "object_is_literal": false,
            "predicate": "https://bago.local/ontology/validates",
            "subject": "https://bago.local/ontology/policy_receipt"
          },
          {
            "evidence_refs": [
              "docs/policy-v1.md#revision=1.0.0",
              "docs/policy-v2.md#revision=2.0.0"
            ],
            "inference_rule": "",
            "inferred": false,
            "object": "https://bago.local/ontology/policy_v1",
            "object_is_literal": false,
            "predicate": "https://bago.local/ontology/supersedes",
            "subject": "https://bago.local/ontology/policy_v2"
          }
        ]
      }
    ],
    "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
    "receipt": {
      "constraints_checked": 1,
      "contradictions_found": 1,
      "cost_usd": 0.0,
      "evidence_refs": [
        "docs/policy-v1.md#revision=1.0.0",
        "docs/policy-v2.md#revision=2.0.0",
        "evidence/policy-receipt.md#revision=1.0.0"
      ],
      "explicit_triples": 41,
      "graph_fingerprint": "744acafe44e20ddb83950b85434000b4d95fda4d56b79d7efc0a923cb7184135",
      "inferred_triples": 3,
      "outcome": "CONSTRAINT_VIOLATION",
      "paths_found": 4,
      "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
      "receipt_id": "ontology_receipt_e29c0d506f581e1b",
      "sparql_queries": [
        "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:supersedes ?object . } LIMIT 50",
        "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:validates ?object . } LIMIT 50",
        "PREFIX bago: <https://bago.local/ontology/> SELECT ?subject ?object WHERE { ?subject bago:validatedBy ?object . } LIMIT 50"
      ]
    },
    "sparql_bindings": [
      {
        "object": "https://bago.local/ontology/policy_v1",
        "subject": "https://bago.local/ontology/policy_v2"
      },
      {
        "object": "https://bago.local/ontology/policy_v2",
        "subject": "https://bago.local/ontology/policy_receipt"
      },
      {
        "object": "https://bago.local/ontology/policy_receipt",
        "subject": "https://bago.local/ontology/policy_v2"
      }
    ],
    "summary": "Ontology Engine (RDF/SPARQL local, coste=0):\nPaths:\n- policy_v2 -[supersedes]-> policy_v1\n- policy_v2 -[validatedBy]-> policy_receipt [inferred]\n- policy_receipt -[validates]-> policy_v2\n- policy_receipt -[validates]-> policy_v2 -[supersedes]-> policy_v1\nInferences: 1 derived triples materialized locally.\nContradictions: 1 explicit conflict relation(s) detected.\nEvidence: docs/policy-v1.md#revision=1.0.0, docs/policy-v2.md#revision=2.0.0, evidence/policy-receipt.md#revision=1.0.0\nReceipt: ontology_receipt_e29c0d506f581e1b outcome=CONSTRAINT_VIOLATION triples=44",
    "violations": [
      {
        "code": "CONTRADICTION",
        "evidence_refs": [
          "docs/candidate-policy.md#revision=0.1.0",
          "docs/policy-v2.md#revision=2.0.0"
        ],
        "message": "Contradictory relation detected between https://bago.local/ontology/candidate_policy and https://bago.local/ontology/policy_v2",
        "severity": "ERROR"
      }
    ]
  },
  "openmetadata_live": "NOT_RUN",
  "query": "¿Qué sustituye a la política anterior y qué evidencia la valida?",
  "scope": "local-rdf-sparql-subset-and-injected-llm-fixture",
  "turtle": "@prefix bago: <https://bago.local/ontology/> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n<https://bago.local/ontology/candidate_policy> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .\n<https://bago.local/ontology/candidate_policy> <http://www.w3.org/2000/01/rdf-schema#label> \"Candidate policy\" .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/authority> \"PROPOSED\" .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/contradicts> <https://bago.local/ontology/policy_v2> .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/description> \"An incompatible experimental policy\" .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/provenance> \"docs/candidate-policy.md\" .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/validity> \"CURRENT\" .\n<https://bago.local/ontology/candidate_policy> <https://bago.local/ontology/version> \"0.1.0\" .\n<https://bago.local/ontology/policy_receipt> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/EVIDENCE> .\n<https://bago.local/ontology/policy_receipt> <http://www.w3.org/2000/01/rdf-schema#label> \"Policy v2 validation receipt\" .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/authority> \"VERIFIED\" .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/description> \"Evidence validating the current policy\" .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/provenance> \"evidence/policy-receipt.md\" .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/source> <https://bago.local/ontology/source_evidence> .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/validates> <https://bago.local/ontology/policy_v2> .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/validity> \"CURRENT\" .\n<https://bago.local/ontology/policy_receipt> <https://bago.local/ontology/version> \"1.0.0\" .\n<https://bago.local/ontology/policy_v1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .\n<https://bago.local/ontology/policy_v1> <http://www.w3.org/2000/01/rdf-schema#label> \"Permit policy v1\" .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/authority> \"CANONICAL\" .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/description> \"Previous permit policy\" .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/provenance> \"docs/policy-v1.md\" .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/supersededBy> <https://bago.local/ontology/policy_v2> .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/validity> \"SUPERSEDED\" .\n<https://bago.local/ontology/policy_v1> <https://bago.local/ontology/version> \"1.0.0\" .\n<https://bago.local/ontology/policy_v2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/CONTRACT> .\n<https://bago.local/ontology/policy_v2> <http://www.w3.org/2000/01/rdf-schema#label> \"Permit policy v2\" .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/authority> \"VERIFIED\" .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/contradicts> <https://bago.local/ontology/candidate_policy> .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/description> \"Current governed permit policy\" .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/provenance> \"docs/policy-v2.md\" .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/source> <https://bago.local/ontology/source_policy> .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/supersedes> <https://bago.local/ontology/policy_v1> .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/validatedBy> <https://bago.local/ontology/policy_receipt> .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/validity> \"CURRENT\" .\n<https://bago.local/ontology/policy_v2> <https://bago.local/ontology/version> \"2.0.0\" .\n<https://bago.local/ontology/source_evidence> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/Source> .\n<https://bago.local/ontology/source_evidence> <http://www.w3.org/2000/01/rdf-schema#label> \"evidence/policy-receipt.md\" .\n<https://bago.local/ontology/source_evidence> <https://bago.local/ontology/uri> \"evidence/policy-receipt.md\" .\n<https://bago.local/ontology/source_policy> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://bago.local/ontology/Source> .\n<https://bago.local/ontology/source_policy> <http://www.w3.org/2000/01/rdf-schema#label> \"docs/policy.md\" .\n<https://bago.local/ontology/source_policy> <https://bago.local/ontology/uri> \"docs/policy.md\" .\n"
}
```
