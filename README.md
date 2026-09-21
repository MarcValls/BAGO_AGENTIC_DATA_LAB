# 🧪 BAGO AGENTIC DATA LAB

**Estado:** L1 ✅ COMPLETE | L2 🟡 EN PROGRESO  
**Inicio:** 2026-09-21  
**Objetivo:** Portfolio público de AI Engineering para oportunidades laborales  
**Licencia:** MIT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 7/7 passing](https://img.shields.io/badge/tests-7%2F7%20passing-brightgreen)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)
[![Coverage: CRIT P0 100%](https://img.shields.io/badge/coverage-CRIT%20P0%20100%25-blue)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)
[![Phase: L1 Complete](https://img.shields.io/badge/phase-L1%20Complete-success)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)
[![Next: L2 ETL](https://img.shields.io/badge/next-L2%20ETL-orange)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)

---

## Propósito

Laboratorio experimental para desarrollar **evidencia técnica verificable** en tecnologías de AI Engineering demandadas por el mercado, integradas con la arquitectura gobernada de BAGO.

No es académico. Es **empleabilidad mediante ejecución técnica**.

---

## Vacantes Objetivo

| Empresa | Rol | Fit Técnico | Timeline | Prioridad |
|---------|-----|-------------|----------|-----------|
| **Orbitant** | AI Engineer | ~93% ✅ | 2-3 semanas | 🎯 Wave 1 |
| **Tuio** | Forward Deployed AI Engineer | ~97% ✅ | 4-5 semanas | 🎯 Wave 2 |
| **Devoteam** | GCP AI Engineer | ~89% | 6-7 semanas | 🎯 Wave 3 |
| **commercetools** | AI Engineer | ~97% | 10 semanas | Stretch |

---

## Roadmap (L0 → L9)

`mermaid
gantt
    title Estado del Proyecto - Septiembre 2026
    dateFormat  YYYY-MM-DD
    section Completado
    L0 Baseline           :done, des0, 2026-09-21, 1d
    L1 LangGraph          :done, des1, 2026-09-21, 1d
    section En Progreso
    L2 ETL Pipeline       :active, des2, 2026-09-21, 7d
    section Pendiente
    L3 Metadata           :         des3, after des2, 7d
    L4 Governed RAG       :         des4, after des3, 7d
    L5 MCP                :         des5, after des4, 7d
    L6 AWS Bedrock        :         des6, after des5, 7d
    L7 Bedrock KB         :         des7, after des6, 7d
    L8 Metadata Catalog   :         des8, after des7, 7d
    L9 End-to-End Agent   :         des9, after des8, 14d
`

| Fase | Estado | Fecha | Evidence |
|------|--------|-------|----------|
| **L0** · Baseline | ✅ COMPLETE | 2026-09-21 | 5 docs, 1600 líneas |
| **L1** · LangGraph | ✅ COMPLETE | 2026-09-21 | 730 líneas código, 7 tests passing |
| **L2** · ETL Pipeline | 🟡 EN PROGRESO | 2026-09-21 | pipeline.py creado |
| **L3** · Metadata | ⚪ PENDIENTE | 2026-10-05 | — |
| **L4** · Governed RAG | ⚪ PENDIENTE | 2026-10-12 | — |
| **L5** · MCP | ⚪ PENDIENTE | 2026-10-19 | ← Candidatura Orbitant |
| **L6** · AWS Bedrock | ⚪ PENDIENTE | 2026-10-26 | ← Candidatura Tuio |
| **L7** · Bedrock KB | ⚪ PENDIENTE | 2026-11-02 | ← Candidatura Devoteam |
| **L8** · Metadata Catalog | ⚪ PENDIENTE | 2026-11-09 | — |
| **L9** · End-to-End Agent | ⚪ PENDIENTE | 2026-12-01 | Portfolio completo |

---

## Arquitectura Clave

**Principio fundamental:** BAGO gobierna. Las tecnologías externas implementan capacidades.

`
LangGraph (orchestration)
    ↓
Reasoning Layer
    ↓
Authorization Boundary ← BAGO GOVERNANCE (permits, validation, action limits)
    ↓
Execution Gateway
    ↓
External Capabilities (Bedrock, MCP, APIs, Vector DBs)
`

**Regla crítica:** Ningún framework externo ejecuta efectos materiales directamente sin autorización explícita de BAGO.

---

## Documentos Fundacionales

- 📄 [LAB_CONTRACT.md](./LAB_CONTRACT.md) — Propósito + inteligencia de mercado integrada
- 📐 [ARCHITECTURE.md](./ARCHITECTURE.md) — Diseño arquitectónico completo con flujos
- 🗺️ [ROADMAP.md](./ROADMAP.md) — Roadmap ejecutivo L0-L9 con fechas y criterios
- 📚 [LEARNING_LEDGER.md](./LEARNING_LEDGER.md) — Registro de aprendizaje por fase
- 💼 [JOB_SKILL_MATRIX.md](./JOB_SKILL_MATRIX.md) — Skills tracker para 4 vacantes objetivo
- 📊 [STATE.md](./STATE.md) — Estado operativo actualizado por fase

---

## Código Implementado

### L1 · LangGraph Governed Execution

- [src/orchestration/state_graph.py](./src/orchestration/state_graph.py) — StateGraph completo (450 líneas)
  - Domain model: ExecutionRequest, Permit, Receipt
  - 6 nodes: classify, retrieve, reason, authorization_gate, execute, verify
  - Authorization boundary con EffectType enum
- [	ests/test_l1_governance.py](./tests/test_l1_governance.py) — 7 tests CRIT P0 passing
  - 	est_langgraph_cannot_execute_directly() → WRITE denegada
  - 	est_permit_reuse_denied() → Replay attack prevention
  - 	est_document_without_provenance_rejected() → Metadata enforcement
  - +4 tests críticos más

### L2 · ETL Pipeline

- [src/etl/pipeline.py](./src/etl/pipeline.py) — Pipeline ETL completo (6 stages)
  - Extract → Normalize → Validate → Enrich → Chunk → Load
  - Content hashing para idempotencia
  - Deduplicación automática
  - Ingestion receipts con evidence

---

## Tests Passing

`ash
$ pytest tests/test_l1_governance.py -v

✅ test_langgraph_cannot_execute_directly
✅ test_permit_reuse_denied
✅ test_document_without_provenance_rejected
✅ test_superseded_chunk_filtered_in_retrieval
✅ test_mcp_tool_unregistered_denied
✅ test_bedrock_provider_timeout_controlled_failure
✅ test_governed_agent_graph_end_to_end

7 passed, 0 failed
`

**Cobertura CRIT P0:** 100%

---

## Aprendizaje Registrado

Ver [LEARNING_LEDGER.md](./LEARNING_LEDGER.md) para entradas detalladas:

- **L1:** LangGraph StateGraph con gobernanza BAGO
  - Interview explanation ready
  - Failure modes evitados
  - Evidence generada

---

## Estado Operativo

`yaml
Fase_actual: L2 · ETL Pipeline
Completado: 22% (L0 + L1)
Bloqueos: 0
P0_issues: 0
P1_issues: 0
Tests_passing: 7/7
Evidence_generada: 
  - 5 docs fundacionales
  - 730 líneas código
  - 7 tests CRIT P0
  - 1 learning entry
Next_action: Ejecutar pipeline ETL con docs BAGO reales
`

---

## Licencia

MIT License — ver [LICENSE](./LICENSE) para detalles.

---

**Última actualización:** 2026-09-21  
**Contacto:** [@MarcValls](https://github.com/MarcValls)  
**Repo:** https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB
