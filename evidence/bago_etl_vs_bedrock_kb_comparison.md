# L7 · BAGO ETL vs Bedrock Knowledge Base

Generated: 2026-09-22 00:19:47 UTC

> Scope: one identical query through the local BAGO ETL/RAG path and an injected Bedrock Knowledge Base client fixture.
> The Bedrock side is not an AWS measurement: no credentials, network, managed KB, cloud latency or current price was used.

## Query

`How does BAGO enforce ExecutionRequest Permit and evidence receipts?`

## Comparison

| Dimension | BAGO ETL + GovernedRAG | Bedrock Knowledge Base fixture |
|---|---|---|
| Retrieval backend | SQLite ETL (65 chunks) + GovernedRAG hybrid | bedrock-agent-runtime fixture |
| Returned references | 3 | 3 |
| Reference overlap | 3/3 | 3/3 |
| Local fixture latency (ms) | 150.207 | 0.106 |
| Authority/provenance | BAGO metadata gate + ETL URI/revision | KB metadata + citation URI normalized by adapter |
| Cost evidence | Local execution; no cloud inference cost | Receipt rate configured as $0.00 fixture; live price NOT_RUN |

## Local BAGO context

Pipeline: `intent_classification, metadata_filters, lexical_bm25, semantic_embedding, hybrid_rrf_fusion, deterministic_reranker, authority_validity_gate, evidence_context_ready`

[1] ad implícita para producir efectos materiales.** Toda acción material debe pasar por: ` ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway ` --- ## Restricciones de Diseño 1. **No sobreajustar BAGO a frameworks externos** - Preferir adapters sobre integración directa - Patrón: BAGO contract → interface → adapter → external technology Evidence: etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl [2] AS** ### Integración Final Un agente capaz de: 1. **Investigar**: Recibir pregunta compleja 2. **Recuperar**: RAG gobernado sobre documentación BAGO + fuentes externas 3. **Razonar**: LangGraph orchestration con múltiples pasos 4. **Proponer herramientas**: MCP tools...

Citations:
- `etl://enrich_norm_file_LAB_CONTRACT_4a9dc8f5#revision=etl`
- `etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl`
- `etl://enrich_norm_file_ROADMAP_2093e19c#revision=etl`

## Bedrock-shaped answer and receipt

BAGO requires an EXTERNAL_API request to pass through a Permit before execution, then records evidence in a receipt.

Citations:
- `s3://fixture-bedrock-kb/enrich_norm_file_LAB_CONTRACT_4a9dc8f5.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_6`
- `s3://fixture-bedrock-kb/enrich_norm_file_ROADMAP_2093e19c.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_ROADMAP_2093e19c_22`
- `s3://fixture-bedrock-kb/enrich_norm_file_ROADMAP_2093e19c.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_ROADMAP_2093e19c_4`

Receipt summary:

```json
{
  "receipt_id": "bedrock_kb_receipt_49f3826a1b5cc7b0",
  "request_id": "bedrock_kb_req_865502edfc6f2407",
  "permit_id": "bedrock_kb_permit_ef86105abc35a29d",
  "knowledge_base_id": "kb-fixture-bago",
  "operation": "retrieve_and_generate",
  "decision": "ALLOW",
  "execution_outcome": "SUCCESS",
  "actual_effect": {
    "called": true,
    "provider": "aws.bedrock",
    "service": "bedrock-agent-runtime",
    "operation": "retrieve_and_generate",
    "knowledge_base_id": "kb-fixture-bago",
    "result_count": 3,
    "attempts": 1
  },
  "evidence_refs": [
    "s3://fixture-bedrock-kb/enrich_norm_file_LAB_CONTRACT_4a9dc8f5.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_LAB_CONTRACT_4a9dc8f5_6",
    "s3://fixture-bedrock-kb/enrich_norm_file_ROADMAP_2093e19c.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_ROADMAP_2093e19c_22",
    "s3://fixture-bedrock-kb/enrich_norm_file_ROADMAP_2093e19c.md?kb=kb-fixture-bago&chunk=chunk_enrich_norm_file_ROADMAP_2093e19c_4"
  ],
  "duration_ms": 0,
  "cost_usd": 0.0,
  "result_count": 3,
  "attempts": 1,
  "error_kind": null,
  "error_message": null
}
```

## Interpretation

- BAGO ETL preserves local control over ingestion, metadata filtering and evidence references.
- Bedrock Knowledge Bases provide managed retrieval/generation, but the provider boundary still needs BAGO permits, allowlists and receipts.
- The matching references prove the comparison contract and citation normalization only; they do not prove equal ranking quality.
- Live AWS validation remains `NOT_RUN` until IAM, data source, vector store, model access and credentials are supplied.
