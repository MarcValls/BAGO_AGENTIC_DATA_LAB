# L9 · Capstone para commercetools

## Objetivo

L9 integra las capacidades del laboratorio en un agente end-to-end que puede:

1. investigar una pregunta;
2. recuperar contexto con RAG gobernado y citas;
3. razonar y proponer una herramienta;
4. pedir un `Permit` antes de cualquier efecto material;
5. ejecutar sólo lecturas MCP o llamadas de proveedor expresamente autorizadas;
6. devolver respuesta, receipts y trazabilidad.

El encaje con commercetools se presenta como evidencia de arquitectura de
agentes: loops acotados, tool use, reglas de negocio, fallos controlados y
evaluación estructural. No se presenta una conexión a una cuenta ni a una API
comercial que no se haya ejecutado.

## Implementación

`src/agent/governed_knowledge_agent.py` compone:

- `GovernedRAG` para intent, filtros de metadata, ranking híbrido y citas;
- `StateGraph` de LangGraph con nodos de clasificación, retrieval, propuesta,
  autorización, ejecución y verificación;
- `GovernedMCPAdapter` para discovery/registry/permit/receipt;
- `GovernedBedrockAdapter` opcional para generación con `toolConfig`, siempre
  detrás de un permit ligado a modelo y request;
- propuestas `CREATE`, `WRITE` y `EXTERNAL_API` que no tienen transporte
  configurado y quedan `PENDING_AUTHORIZATION`.

## Tres escenarios

| Escenario | Resultado gobernado |
|---|---|
| Pregunta técnica sobre `session_manager` | RAG + citas; MCP `READ` opcional; Bedrock fixture opcional |
| Crear un test de `workspace_binding` | propone `file_creator` y MCP `WRITE`; no modifica archivos |
| Comprobar canon RC6 | genera informe con evidencia y propone issue; no llama GitHub |

La evidencia reproducible está en
`evidence/l9_commercetools_agent.md` y se genera con:

```bash
python scripts/generate_l9_agent_evidence.py
```

## Boundary de validación

La evidencia actual es `VERIFIED` para el flujo offline y el servidor MCP local.
El cliente Bedrock es un fixture inyectado. AWS real, una cuenta/API de
commercetools, creación real de issues y evaluación con tráfico de producción
permanecen `NOT_RUN` hasta disponer de identidad, permisos y un entorno de
integración explícitamente autorizado.
