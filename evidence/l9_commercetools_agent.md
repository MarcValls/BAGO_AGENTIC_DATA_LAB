# L9 · Governed Knowledge Agent — commercetools portfolio evidence

Generated at: `2026-09-22T01:28:26.604103+00:00`

This artifact validates the end-to-end governed orchestration offline.
The target is the commercetools AI Engineer portfolio scenario; no
commercial commercetools API or production AWS account is contacted.

## Boundary

```text
LangGraph → governed RAG → proposal → Permit → optional MCP/Bedrock → receipt
                         └→ human approval for CREATE / WRITE / external issue
```

- Retrieval corpus: `68` L2 chunks
- Bedrock calls: `1` injected fixture call
- MCP transport: `local_stdio_server`
- AWS live, commercetools live and GitHub issue creation: `NOT_RUN`

## Scenarios

1. Technical query: `COMPLETED`; citations=`5`; MCP READ and Bedrock fixture receipts present.
2. Implementation query: `PENDING_AUTHORIZATION`; CREATE and MCP WRITE proposals have no transport call and leave decision receipts.
3. Architecture query: `PENDING_AUTHORIZATION`; GitHub issue proposal leaves a `called=false` decision receipt.

## Reproducible command

```bash
python scripts/generate_l9_agent_evidence.py
```

## Full result

```json
{
  "bedrock_fixture_calls": 1,
  "bedrock_transport": "injected_fixture_no_aws_call",
  "generated_at": "2026-09-22T01:28:26.604103+00:00",
  "mcp_transport": "local_stdio_server",
  "retrieval_chunks": 68,
  "scenarios": {
    "architecture_query": {
      "answer": "Respuesta construida con retrieval gobernado:\n- ejecutar test (gobernado)\n   - Muestra resultado\n\n3. **Query de arquitectura**: \"¿BAGO cumple el canon RC6?\"\n   - Recupera canon + código actual\n   - Compara punto por punto\n   - Genera reporte de gaps\n   - Crea issues en GitHub (gobernado)\n\n### Entregables\n\n- [ ] src/agent/governed_knowledge_agent.py\n- [ ] \tests/test_end_to_end_agent.py\n- [ ] README.md final con demos grabadas\n- [ ] Portfolio público completo en GitHub\n\n---\n\n## JOB SKILL MATRIX — Progreso por Fase\n- RC6 architecture review retrieves canon evidence and may propose a GitHub issue, but external issue creation remains pending human authorization.\n- ha objetivo:** 2026-10-05\n\n### Corpus de Ingesta\n\nDocumentación pública de BAGO:\n- AGENTS.md\n- CANON_BAGO_1.0-RC6.md\n- Docs de backend/\n- Docs de frontend/\n\n### Pipeline a Implementar\n\nSe preparó un informe de gaps; no se envió ningún issue externo sin autorización explícita.\n\nEvidence:\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- docs/commercetools_capstone.md#scenario=architecture#revision=l9\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl\n- docs/commercetools_capstone.md#scenario=implementation#revision=l9",
      "citations": [
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "docs/commercetools_capstone.md#scenario=architecture#revision=l9",
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
        "docs/commercetools_capstone.md#scenario=implementation#revision=l9"
      ],
      "decision_receipts": [
        {
          "actual_effect": {
            "called": false,
            "tool": "github.create_issue",
            "transport": "none"
          },
          "decision": "REQUIRE_HUMAN",
          "error_message": "Material effect requires explicit human authorization",
          "evidence_refs": [
            "agent://github.create_issue#request=agent_request_6059db384b388847"
          ],
          "execution_outcome": "FAILURE",
          "receipt_id": "agent_receipt_20d6a34f02e04c84",
          "request_id": "agent_request_6059db384b388847",
          "tool_name": "github.create_issue"
        }
      ],
      "errors": [],
      "intent": "retrieval",
      "mcp_receipts": [],
      "proposals": [
        {
          "arguments": {
            "body": "Offline BAGO architecture review. Evidence was retrieved through the governed RAG boundary. Citations: etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl, docs/commercetools_capstone.md#scenario=architecture#revision=l9, etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl, etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl, docs/commercetools_capstone.md#scenario=implementation#revision=l9. Human review is required before creating an external issue.",
            "title": "BAGO canon compliance review"
          },
          "called": false,
          "context_revision": "l9-demo-v1",
          "decision": "REQUIRE_HUMAN",
          "effect_type": "EXTERNAL_API",
          "error_message": "Material effect requires explicit human authorization",
          "outcome": "FAILURE",
          "permit_id": "",
          "proposal_id": "proposal_c81db96a5ace164d",
          "rationale": "Creating a GitHub issue is external and requires explicit approval.",
          "receipt_id": "agent_receipt_20d6a34f02e04c84",
          "request_id": "agent_request_6059db384b388847",
          "result": null,
          "tool_name": "github.create_issue",
          "transport": "none"
        }
      ],
      "provider_receipt": null,
      "provider_text": null,
      "query": "¿BAGO cumple el canon RC6?",
      "retrieval": {
        "citations": [
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "docs/commercetools_capstone.md#scenario=architecture#revision=l9",
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
          "docs/commercetools_capstone.md#scenario=implementation#revision=l9"
        ],
        "eligible_count": 68,
        "filtered_count": 0,
        "hits": [
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_24",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_24",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 11.96259472,
            "rank": 1,
            "score": 1.31238194,
            "semantic_score": 0.20861466
          },
          {
            "chunk_id": "l9-architecture",
            "document_id": "commercetools-capstone",
            "evidence": {
              "chunk_id": "l9-architecture",
              "citation": "docs/commercetools_capstone.md#scenario=architecture#revision=l9",
              "document_id": "commercetools-capstone",
              "revision": "l9",
              "source_uri": "docs/commercetools_capstone.md#scenario=architecture"
            },
            "lexical_score": 7.81486431,
            "rank": 2,
            "score": 0.89180571,
            "semantic_score": 0.14785315
          },
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_6",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_6",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 5.25368543,
            "rank": 3,
            "score": 0.74609293,
            "semantic_score": 0.14581851
          },
          {
            "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_0",
            "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_0",
              "citation": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
              "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5"
            },
            "lexical_score": 1.81080667,
            "rank": 4,
            "score": 0.55815191,
            "semantic_score": 0.15129958
          },
          {
            "chunk_id": "l9-implementation",
            "document_id": "commercetools-capstone",
            "evidence": {
              "chunk_id": "l9-implementation",
              "citation": "docs/commercetools_capstone.md#scenario=implementation#revision=l9",
              "document_id": "commercetools-capstone",
              "revision": "l9",
              "source_uri": "docs/commercetools_capstone.md#scenario=implementation"
            },
            "lexical_score": 1.66830419,
            "rank": 5,
            "score": 0.5473966,
            "semantic_score": 0.14966986
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
        "query": "¿BAGO cumple el canon RC6?",
        "reranked": true
      },
      "run_id": "agent_run_5ffdf303d7e6f033",
      "status": "PENDING_AUTHORIZATION",
      "trace": [
        "classify_intent=retrieval; entities=BAGO,RC6",
        "retrieve_context=hits:5; filtered:0",
        "reason_and_propose=proposals:1",
        "authorize=github.create_issue:REQUIRE_HUMAN:no_transport",
        "verify_and_respond=status:PENDING_AUTHORIZATION; citations:5"
      ]
    },
    "implementation_query": {
      "answer": "Respuesta construida con retrieval gobernado:\n- eceipts + evidence links\n\n### Escenarios de Demo\n\n1. **Query técnica**: \"¿Cómo funciona session_manager en BAGO?\"\n   - Recupera docs oficiales\n   - Responde con citations\n   - Ofrece abrir archivos relevantes (gobernado)\n\n2. **Query de implementación**: \"Crea un test para workspace_binding\"\n   - Recupera código existente\n   - Genera test scaffold\n   - Propone ejecutar test (gobernado)\n   - Muestra resultado\n- workspace_binding test generation produces a CREATE proposal; BAGO requires human authorization and does not write the file automatically.\n- ejecutar test (gobernado)\n   - Muestra resultado\n\n3. **Query de arquitectura**: \"¿BAGO cumple el canon RC6?\"\n   - Recupera canon + código actual\n   - Compara punto por punto\n   - Genera reporte de gaps\n   - Crea issues en GitHub (gobernado)\n\n### Entregables\n\n- [ ] src/agent/governed_knowledge_agent.py\n- [ ] \tests/test_end_to_end_agent.py\n- [ ] README.md final con demos grabadas\n- [ ] Portfolio público completo en GitHub\n\n---\n\n## JOB SKILL MATRIX — Progreso por Fase\n\nSe preparó una propuesta de test; no se creó ningún archivo porque CREATE requiere autorización humana.\n\nEvidence:\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- docs/commercetools_capstone.md#scenario=implementation#revision=l9\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
      "citations": [
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "docs/commercetools_capstone.md#scenario=implementation#revision=l9",
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl"
      ],
      "decision_receipts": [
        {
          "actual_effect": {
            "called": false,
            "tool": "file_creator",
            "transport": "none"
          },
          "decision": "REQUIRE_HUMAN",
          "error_message": "Material effect requires explicit human authorization",
          "evidence_refs": [
            "agent://file_creator#request=agent_request_179b57096a0c845f"
          ],
          "execution_outcome": "FAILURE",
          "receipt_id": "agent_receipt_c709bab7ab940b75",
          "request_id": "agent_request_179b57096a0c845f",
          "tool_name": "file_creator"
        }
      ],
      "errors": [],
      "intent": "action",
      "mcp_receipts": [
        {
          "actual_effect": {
            "called": false,
            "server": "bago-local-demo",
            "tool": "propose_lab_note"
          },
          "decision": "REQUIRE_HUMAN",
          "duration_ms": 0,
          "error_message": "DENY: permit decision is REQUIRE_HUMAN",
          "evidence_refs": [
            "mcp://bago-local-demo/tools/propose_lab_note#request=mcp_req_3fa93b04f1044b36"
          ],
          "execution_outcome": "FAILURE",
          "permit_id": "mcp_permit_71e4a0e30554cc85",
          "receipt_id": "mcp_receipt_cb7eba1de751ac62",
          "request_id": "mcp_req_3fa93b04f1044b36",
          "result": null,
          "server_name": "bago-local-demo",
          "tool_name": "propose_lab_note"
        }
      ],
      "proposals": [
        {
          "arguments": {
            "content": "def test_workspace_binding_contract():\n    assert workspace_binding_is_governed()\n",
            "path": "tests/test_workspace_binding.py"
          },
          "called": false,
          "context_revision": "l9-demo-v1",
          "decision": "REQUIRE_HUMAN",
          "effect_type": "CREATE",
          "error_message": "Material effect requires explicit human authorization",
          "outcome": "FAILURE",
          "permit_id": "",
          "proposal_id": "proposal_38c0d7283aa7f710",
          "rationale": "A generated test is a CREATE effect and needs human approval.",
          "receipt_id": "agent_receipt_c709bab7ab940b75",
          "request_id": "agent_request_179b57096a0c845f",
          "result": null,
          "tool_name": "file_creator",
          "transport": "none"
        },
        {
          "arguments": {
            "content": "def test_workspace_binding_contract():\n    assert workspace_binding_is_governed()\n",
            "path": "notes/l9-test-proposal.md"
          },
          "called": false,
          "context_revision": "l9-demo-v1",
          "decision": "REQUIRE_HUMAN",
          "effect_type": "WRITE",
          "error_message": "DENY: permit decision is REQUIRE_HUMAN",
          "outcome": "FAILURE",
          "permit_id": "mcp_permit_71e4a0e30554cc85",
          "proposal_id": "proposal_3b21f5940f74a34f",
          "rationale": "Demonstrate that an MCP WRITE is blocked before transport.",
          "receipt_id": "mcp_receipt_cb7eba1de751ac62",
          "request_id": "mcp_req_3fa93b04f1044b36",
          "result": null,
          "tool_name": "propose_lab_note",
          "transport": "mcp"
        }
      ],
      "provider_receipt": null,
      "provider_text": null,
      "query": "Crea un test para workspace_binding",
      "retrieval": {
        "citations": [
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "docs/commercetools_capstone.md#scenario=implementation#revision=l9",
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl"
        ],
        "eligible_count": 68,
        "filtered_count": 0,
        "hits": [
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_23",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_23",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 10.98130288,
            "rank": 1,
            "score": 1.28980163,
            "semantic_score": 0.23736013
          },
          {
            "chunk_id": "l9-implementation",
            "document_id": "commercetools-capstone",
            "evidence": {
              "chunk_id": "l9-implementation",
              "citation": "docs/commercetools_capstone.md#scenario=implementation#revision=l9",
              "document_id": "commercetools-capstone",
              "revision": "l9",
              "source_uri": "docs/commercetools_capstone.md#scenario=implementation"
            },
            "lexical_score": 7.43903679,
            "rank": 2,
            "score": 0.92790082,
            "semantic_score": 0.21435839
          },
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_24",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_24",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 4.89252225,
            "rank": 3,
            "score": 0.72702912,
            "semantic_score": 0.16845198
          },
          {
            "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_12",
            "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_12",
              "citation": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
              "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5"
            },
            "lexical_score": 2.28402224,
            "rank": 4,
            "score": 0.57700937,
            "semantic_score": 0.17995638
          },
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_9",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_9",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 2.14556374,
            "rank": 5,
            "score": 0.49558046,
            "semantic_score": 0.11778307
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
        "query": "Crea un test para workspace_binding",
        "reranked": true
      },
      "run_id": "agent_run_d6018358a4da3f7c",
      "status": "PENDING_AUTHORIZATION",
      "trace": [
        "classify_intent=action; entities=workspace_binding",
        "retrieve_context=hits:5; filtered:0",
        "reason_and_propose=proposals:2",
        "authorize=file_creator:REQUIRE_HUMAN:no_transport",
        "authorize=propose_lab_note:REQUIRE_HUMAN:permit=mcp_permit_71e4a0e30554cc85",
        "verify_and_respond=status:PENDING_AUTHORIZATION; citations:5"
      ]
    },
    "technical_query": {
      "answer": "Fixture Bedrock answer generated from governed context; BAGO retains action authority and citations.\n\nEvidence:\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- docs/commercetools_capstone.md#scenario=technical#revision=l9\n- etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl\n- etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n- etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
      "citations": [
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "docs/commercetools_capstone.md#scenario=technical#revision=l9",
        "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
        "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
        "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl"
      ],
      "decision_receipts": [],
      "errors": [],
      "intent": "reasoning",
      "mcp_receipts": [
        {
          "actual_effect": {
            "called": true,
            "server": "bago-local-demo",
            "tool": "get_lab_status"
          },
          "decision": "ALLOW",
          "duration_ms": 7,
          "error_message": null,
          "evidence_refs": [
            "mcp://bago-local-demo/tools/get_lab_status#request=mcp_req_4fe4f0ba0edebf01"
          ],
          "execution_outcome": "SUCCESS",
          "permit_id": "mcp_permit_7661ea9f3e4ffbf9",
          "receipt_id": "mcp_receipt_d6a9a21efb63bdb9",
          "request_id": "mcp_req_4fe4f0ba0edebf01",
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
        }
      ],
      "proposals": [
        {
          "arguments": {},
          "called": true,
          "context_revision": "l9-demo-v1",
          "decision": "ALLOW",
          "effect_type": "READ",
          "error_message": null,
          "outcome": "SUCCESS",
          "permit_id": "mcp_permit_7661ea9f3e4ffbf9",
          "proposal_id": "proposal_e7ae4dbb94800c7b",
          "rationale": "Read-only status may enrich a technical answer.",
          "receipt_id": "mcp_receipt_d6a9a21efb63bdb9",
          "request_id": "mcp_req_4fe4f0ba0edebf01",
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
          "tool_name": "get_lab_status",
          "transport": "mcp"
        },
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
                    "text": "Question: ¿Cómo funciona session_manager en BAGO?\n\nGoverned context:\n[1] eceipts + evidence links\n\n### Escenarios de Demo\n\n1. **Query técnica**: \"¿Cómo funciona session_manager en BAGO?\"\n   - Recupera docs oficiales\n   - Responde con citations\n   - Ofrece abrir archivos relevantes (gobernado)\n\n2. **Query de implementación**: \"Crea un test para workspace_binding\"\n   - Recupera código existente\n   - Genera test scaffold\n   - Propone ejecutar test (gobernado)\n   - Muestra resultado\nEvidence: etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n\n[2] session_manager is answered through governed LangGraph orchestration, hybrid RAG retrieval, citations and an optional read-only MCP status call.\nEvidence: docs/commercetools_capstone.md#scenario=technical#revision=l9\n\n[3] etadata, lineage)\n✅ **Observabilidad** y tracing\n\n**Conclusión arquitectónica:** El trabajo desarrollado en BAGO coincide directamente con los requisitos. Los gaps son **tecnológicos concretos**, no conceptuales.\n\n---\n\n## Principio Arquitectónico Fundamental\n\n**BAGO gobierna. Las tecnologías externas implementan capacidades.**\n\nNunca asumir:\n`\nframework externo = autoridad\n`\nEvidence: etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl\n\n[4] bjetivo:** 2026-10-19\n\n### Pipeline de Retrieval\n\n`\nQUERY\n  ↓\nINTENT (classification: retrieval vs reasoning vs action)\n  ↓\nMETADATA FILTERS (authority >= X, date >= Y, domain in Z)\n  ↓\nLEXICAL RETRIEVAL (BM25, top-k=50)\n  ↓\nSEMANTIC RETRIEVAL (embeddings, top-k=50)\n  ↓\nRERANKING (cross-encoder, top-k=10)\n  ↓\nAUTHORITY FILTERING (BAGO governance rules)\n  ↓\nCONTEXT ASSEMBLY (prompt construction con citations)\n  ↓\nGENERATION (LLM response)\n  ↓\nEVIDENCE (claim → chunk → source → revision mapping)\n`\nEvidence: etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl\n\n[5] ad implícita para producir efectos materiales.**\n\nToda acción material debe pasar por:\n`\nExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway\n`\n\n---\n\n## Restricciones de Diseño\n\n1. **No sobreajustar BAGO a frameworks externos**\n   - Preferir adapters sobre integración directa\n   - Patrón: BAGO contract → interface → adapter → external technology\nEvidence: etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl\n\n\nReturn a concise answer with no unsupported claims."
                  }
                ],
                "role": "user"
              }
            ],
            "model_id": "fixture.l9-model",
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
          "context_revision": "l9-demo-v1",
          "decision": "ALLOW",
          "effect_type": "EXTERNAL_API",
          "error_message": null,
          "outcome": "SUCCESS",
          "permit_id": "bedrock_permit_13787e577c1d7af8",
          "proposal_id": "proposal_34ff116d1580b3df",
          "rationale": "Provider generation is a separately governed external call.",
          "receipt_id": "bedrock_receipt_f21f7cee33f9cbd2",
          "request_id": "bedrock_req_252745b1dcad58ca",
          "result": "Fixture Bedrock answer generated from governed context; BAGO retains action authority and citations.",
          "tool_name": "bedrock.converse",
          "transport": "bedrock"
        }
      ],
      "provider_receipt": {
        "actual_effect": {
          "attempts": 1,
          "called": true,
          "model_id": "fixture.l9-model",
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
          "bedrock://eu-west-1/fixture.l9-model/converse#request=bedrock_req_252745b1dcad58ca"
        ],
        "execution_outcome": "SUCCESS",
        "model_id": "fixture.l9-model",
        "operation": "converse",
        "permit_id": "bedrock_permit_13787e577c1d7af8",
        "receipt_id": "bedrock_receipt_f21f7cee33f9cbd2",
        "request_id": "bedrock_req_252745b1dcad58ca",
        "usage": {
          "input_tokens": 32,
          "output_tokens": 18,
          "total_tokens": 50
        }
      },
      "provider_text": "Fixture Bedrock answer generated from governed context; BAGO retains action authority and citations.",
      "query": "¿Cómo funciona session_manager en BAGO?",
      "retrieval": {
        "citations": [
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "docs/commercetools_capstone.md#scenario=technical#revision=l9",
          "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
          "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
          "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl"
        ],
        "eligible_count": 68,
        "filtered_count": 0,
        "hits": [
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_23",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_23",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 9.21322917,
            "rank": 1,
            "score": 1.24422241,
            "semantic_score": 0.2175787
          },
          {
            "chunk_id": "l9-technical",
            "document_id": "commercetools-capstone",
            "evidence": {
              "chunk_id": "l9-technical",
              "citation": "docs/commercetools_capstone.md#scenario=technical#revision=l9",
              "document_id": "commercetools-capstone",
              "revision": "l9",
              "source_uri": "docs/commercetools_capstone.md#scenario=technical"
            },
            "lexical_score": 4.34842207,
            "rank": 2,
            "score": 0.79958202,
            "semantic_score": 0.24596127
          },
          {
            "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_4",
            "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_4",
              "citation": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
              "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5"
            },
            "lexical_score": 1.82693365,
            "rank": 3,
            "score": 0.49504624,
            "semantic_score": 0.11660606
          },
          {
            "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_13",
            "document_id": "enrich_norm_file_ROADMAP_2093e19c",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_ROADMAP_2093e19c_13",
              "citation": "etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl",
              "document_id": "enrich_norm_file_ROADMAP_2093e19c",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_ROADMAP_2093e19c"
            },
            "lexical_score": 1.02077623,
            "rank": 4,
            "score": 0.47101545,
            "semantic_score": 0.16075445
          },
          {
            "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_6",
            "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
            "evidence": {
              "chunk_id": "chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_6",
              "citation": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl",
              "document_id": "enrich_norm_file_LAB_CONTRACT_4a9dc8f5",
              "revision": "etl",
              "source_uri": "etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5"
            },
            "lexical_score": 1.81080667,
            "rank": 5,
            "score": 0.47065092,
            "semantic_score": 0.09180505
          }
        ],
        "intent": "reasoning",
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
        "query": "¿Cómo funciona session_manager en BAGO?",
        "reranked": true
      },
      "run_id": "agent_run_f1e94b88af25d9d7",
      "status": "COMPLETED",
      "trace": [
        "classify_intent=reasoning; entities=BAGO,session_manager",
        "retrieve_context=hits:5; filtered:0",
        "reason_and_propose=proposals:2",
        "authorize=get_lab_status:ALLOW:permit=mcp_permit_7661ea9f3e4ffbf9",
        "authorize=bedrock.converse:ALLOW:permit=bedrock_permit_13787e577c1d7af8",
        "execute=get_lab_status:SUCCESS",
        "execute=bedrock.converse:SUCCESS",
        "verify_and_respond=status:COMPLETED; citations:5"
      ]
    }
  },
  "scope": "offline-fixture-and-local-mcp"
}
```
