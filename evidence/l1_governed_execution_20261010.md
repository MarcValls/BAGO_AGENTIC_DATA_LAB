# Reauditoría L1 — LangGraph Governed Execution

**Estado de la auditoría:** `VALIDATED` como evidencia local del alcance probado.
**Estado de la fase L1:** `PARTIAL (local evidence)`.
**Candidato ejecutado:** `defe7b80840082c0ad2749c2ea17af443b87a055` en `codex/l1-governed-execution-evidence-20261010`.
**Base:** `325cab5a334674f1d1528762490a4dea3bb05a7b`.

## Qué demuestra

La auditoría encontró que los siete tests de referencia originales incluían comprobaciones definidas dentro del propio test y no ejercitaban todas las garantías que sus nombres sugerían. En el candidato actual, la suite los reemplaza por pruebas que atraviesan límites reales de producción. El grafo L1 deniega los efectos distintos de READ y ya no crea efectos ni recibos aleatorios: como no tiene enlazado un `ExecutionGateway`, deja constancia de que no ejecutó el permiso.

Los controles sandbox, retrieval, MCP y Bedrock existen y se ejercitan por separado. Su existencia no demuestra que el StateGraph los integre. Por eso la afirmación amplia de L1 permanece `PARTIAL`.

## Mapa de pruebas de referencia

| Caso | Límite real ejercitado | Resultado y límite |
|---|---|---|
| `test_langgraph_cannot_execute_directly` | Grafo compilado y `authorization_gate` | `PASS`: WRITE, CREATE, DELETE, EXTERNAL_API y EXTERNAL_TOOL quedan denegados sin permisos. No demuestra ejecución con autorización humana. |
| `test_permit_reuse_denied` | `ExecutionGateway` y `SandboxManager.execute` | `PASS`: segundo uso dentro de una instancia produce `PERMIT_REPLAY`. El registro de replay es en memoria, no persistente entre procesos. |
| `test_document_without_provenance_rejected` | `GovernedRAG.retrieve` | `PASS`: un chunk sin URI/procedencia o revisión queda filtrado. No exige `created_at`; la ingesta puede sintetizar URI/revisión. |
| `test_superseded_chunk_filtered_in_retrieval` | Filtro de metadata de `GovernedRAG` | `PASS`: `SUPERSEDED` se excluye antes del ranking cuando aplica el filtro predeterminado configurado en el caso. |
| `test_mcp_tool_unregistered_denied` | `GovernedMCPAdapter.call` | `PASS`: herramienta descubierta pero no registrada se deniega antes del transporte; el test verifica cero llamadas. |
| `test_bedrock_provider_timeout_controlled_failure` | `BedrockProviderAdapter.converse` | `PASS` acotado al manejo de una excepción `TimeoutError` inyectada, sus reintentos y recibo `FAILURE/TIMEOUT`. No demuestra que el timeout del cliente AWS interrumpa una llamada lenta ni llama a AWS. |
| `test_governed_agent_graph_end_to_end` | Grafo compilado L1 | `PARTIAL`: completa la consulta segura con retrieval fixture local; no integra `GovernedRAG`, `ExecutionGateway` ni proveedores reales. |

Prueba adicional: `test_unbound_graph_executor_does_not_fabricate_success_receipt` confirma que un permiso válido no produce un recibo de éxito cuando el gateway no está enlazado.

## Ejecuciones y revisión

Los recibos de consola completos están en `evidence/l1-governed-execution-20261010/`.

- `python -m pytest tests/test_l1_governance.py -q`: **8 passed**, 1 warning.
- `python -m pytest tests/test_sandbox.py tests/test_retrieval_accuracy.py tests/test_mcp_governance.py tests/test_bedrock_integration.py -q`: **40 passed**, 1 warning.
- `python -m pytest tests -q`: **203 passed**, 1 warning, 65.14 s.
- `python scripts/generate_dynamic_readme.py`: terminó y generó README para **203 tests**.
- `python scripts/generate_dynamic_readme.py --check --skip-tests`: **README verificado (203 tests)**.
- `git diff --check`: terminó sin errores.
- Aviso común: `langchain_core` advierte que su funcionalidad Pydantic V1 no es compatible con Python 3.14 o posterior.
- Revisión independiente de solo lectura sobre `defe7b8`: no encontró P0/P1 dentro de los claims `PASS` mientras se conserven los límites documentados. Identificó el README obsoleto antes de regenerarlo; el README final y su check están incluidos en el candidato.
- `python .bago/bin/bago.py verify`: `NOT_RUN`; este repositorio no contiene `.bago/bin/bago.py`.

## Identidad y huellas

Las huellas SHA-256 corresponden al contenido incluido en el commit `defe7b8`:

| Archivo | SHA-256 |
|---|---|
| `src/orchestration/state_graph.py` | `f52b73704b35a4b5e4f49a66a6723fef0a7c6b25ef54dc45d0685743f27809e3` |
| `tests/test_l1_governance.py` | `bbbd7c24f804d6a84705ac126c63dadf98e81ff4c55d399823ddb921c08cde6c` |
| `tests/test_dynamic_readme.py` | `d827362153ca97c5e53dbba7c85912b92105ef8e3c8768b21751b82563d7b136` |
| `docs/readme_manifest.json` | `ab2a7e4a6b0bdcf9084a976c15b2517e7209be6b059e452cd7a91ac6da3c6ed1` |
| `.bago/canon/STATE.md` | `db8c2695b2e9b8613f29b3748132f34b9d83056635c137173a811c34261453ff` |
| `.bago/canon/JOB_SKILL_MATRIX.md` | `78862e3f0fea030855d506d851ec8dca6900bfc6e0d8bed0ce515d6b1a6830ab` |
| `README.md` | `af54de293a4555d4e96fc7652a4a9f4e3e2dcb361656b3b79318a743d3d21a11` |

| Recibo | SHA-256 |
|---|---|
| `evidence/l1-governed-execution-20261010/L1_TESTS.txt` | `1f24cfadb9a66e543adf9b22226bb72c257afad75f9f598351ac2570c7fba0e6` |
| `evidence/l1-governed-execution-20261010/REGRESSION_TESTS.txt` | `a02f4c22aec0d34286882b2d2ab9cf1b9cf9a6e1ac95e63ba9d8b95793d46598` |
| `evidence/l1-governed-execution-20261010/FULL_SUITE.txt` | `db25d5bd6be028d2ccc47dd31990219874e43a30a16ed5145b7ee6509c86919f` |
| `evidence/l1-governed-execution-20261010/README_GENERATION.txt` | `4cc6b25ced6d6481baba24a7cc0e2e71a869e355963194306bf81385bb415522` |
| `evidence/l1-governed-execution-20261010/README_CHECK.txt` | `c8c0c35d0796779ccb22b7ba1de06286130976676a0c8e8460a1477d845dac10` |

## Cierre

El goal `L1-GOVERNED-EXECUTION-EVIDENCE-001` queda `VALIDATED` para la auditoría y evidencia local de los claims delimitados. Esto **no** promueve la fase L1 a `VALIDATED`: siguen sin demostrarse la integración del StateGraph con gateway/sandbox/RAG/adapters, el anti-replay persistente, llamadas remotas MCP/Bedrock y el aislamiento real de red del sandbox.
