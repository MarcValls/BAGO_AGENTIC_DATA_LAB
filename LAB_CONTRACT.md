# BAGO AGENTIC DATA LAB — Contrato del Laboratorio

## Propósito

Este laboratorio existe para desarrollar **evidencia técnica pública y verificable** en tecnologías de AI Engineering demandadas por el mercado, integradas arquitectónicamente con BAGO.

No es un proyecto académico. Es un **programa de empleabilidad mediante ejecución técnica**.

---

## Objetivos Simultáneos

1. **Aprender** tecnologías demandadas actualmente por el mercado de AI Engineering
2. **Integrarlas** de forma arquitectónicamente correcta con BAGO
3. **Producir evidencia** técnica pública que pueda utilizarse profesionalmente

---

## Inteligencia de Mercado (Septiembre 2026)

### Vacantes Prioritarias Identificadas

| Empresa | Rol | Fit Técnico | Gap Principal | Timeline |
|---------|-----|-------------|---------------|----------|
| **Tuio** | Forward Deployed AI Engineer | ~96% | Seniority (~5 años) | 4-5 semanas |
| **Orbitant** | AI Engineer | ~91% | LangGraph + Cloud | 2-3 semanas |
| **Devoteam** | GCP AI Engineer (Gemini) | ~87% → 93% | Vertex AI / GCP | 6-7 semanas |
| **commercetools** | AI Engineer | ~97% | Seniority + LLM production | Stretch goal |

### Patrón Común de Requisitos

Las 4 vacantes comparten explícitamente:

✅ **Agentes y orchestration** (LangGraph/LangChain)
✅ **Tool calling / MCP**
✅ **RAG + retrieval híbrido**
✅ **Validaciones y permisos** (action limits, human escalation)
✅ **Testing y evaluación** de sistemas LLM
✅ **Pipelines de datos** (ETL, metadata, lineage)
✅ **Observabilidad** y tracing

**Conclusión arquitectónica:** El trabajo desarrollado en BAGO coincide directamente con los requisitos. Los gaps son **tecnológicos concretos**, no conceptuales.

---

## Principio Arquitectónico Fundamental

**BAGO gobierna. Las tecnologías externas implementan capacidades.**

Nunca asumir:
`
framework externo = autoridad
`

Mantener siempre la separación:
`
reasoning may propose
authorization decides
ExecutionGateway executes
evidence proves what happened
`

- LangGraph podrá orquestar
- Bedrock podrá inferir
- MCP podrá exponer herramientas
- ETL podrá transformar datos
- RAG podrá recuperar información

**Pero ninguna de esas capas adquiere autoridad implícita para producir efectos materiales.**

Toda acción material debe pasar por:
`
ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway
`

---

## Restricciones de Diseño

1. **No sobreajustar BAGO a frameworks externos**
   - Preferir adapters sobre integración directa
   - Patrón: BAGO contract → interface → adapter → external technology

2. **Separar LAB experimental de BAGO canónico**
   - LAB = experimental, validación rápida
   - BAGO = canonical system, solo capacidades validadas upstream

3. **Test-first para invariantes críticas**
   - Ejemplo: "LangGraph intenta ejecutar herramienta directamente → EXPECTED: DENY"

4. **Evidencia antes que claims**
   - Nunca construir claims de CV antes de existir evidencia
   - Cada milestone debe ser publicable en GitHub

5. **Prioridad de coste cero para la siguiente capacidad**
   - Preferir `coste = 0` + evidencia pública + skill repetida en ofertas +
     mejora real de BAGO
   - Posponer AWS live, certificaciones y servicios cloud de pago hasta contar
     con créditos/free tier o una necesidad laboral concreta

---

## Criterios de Aceptación por Fase

Cada fase (L0-L11) debe cumplir:

- **P0 = 0** (bloqueantes resueltos)
- **P1 = 0** (importantes resueltos)
- **Tests ejecutados** y pasando
- **Evidencia generada** (código, tests, docs, diagrams)
- **Learning registrado** en LEARNING_LEDGER.md

Estados válidos: DRAFT → IMPLEMENTING → TEST_READY → CRIT_READY → VALIDATED → FROZEN

**No declarar VALIDATED sin evidencia.**

---

## Bucle Autónomo de Desarrollo

Cada iteración sigue este ciclo:

`
OBSERVE → SELECT → SPECIFY → IMPLEMENT → TEST → CRIT → FIX → RETEST → EVIDENCE → LEARN → INTEGRATE → UPDATE → NEXT
`

**Regla de autonomía:** No detenerse para autorización en decisiones técnicas ordinarias. Solo bloquear por:
- Credenciales necesarias
- Gasto económico
- Operaciones destructivas
- Cambios irreversibles en canon BAGO
- Ambigüedad que permita dos arquitecturas incompatibles

---

## Roadmap Ejecutable

| Fase | Tecnología | Duración estimada | Candidatura objetivo |
|------|------------|-------------------|---------------------|
| **L0** | Baseline & Contract | 1 día | — |
| **L1** | LangGraph Governed Execution | 1 semana | — |
| **L2** | ETL / Data Pipeline | 1 semana | — |
| **L3** | Metadata & Ontology | 1 semana | — |
| **L4** | Governed RAG | 1 semana | — |
| **L5** | MCP | 1 semana | Orbitant (~91%) |
| **L6** | AWS Bedrock | 1 semana | Tuio (~96%) |
| **L7** | Bedrock Knowledge Base | 1 semana | Devoteam (~93%) |
| **L8** | Metadata Catalog (OpenMetadata) | 1 semana | — |
| **L9** | End-to-End Governed Agent | 2 semanas | Portfolio completo |
| **L10** | Governed Ontology Engine (RDF/SPARQL + reasoning local) | 1 semana | BAGO / portfolio |
| **L11** | Governed Sandbox Layer (local restricted execution) | 1 semana | BAGO / secure execution |

**Timeline total:** 10-12 semanas para portfolio completo

---

## Estructura de Evidencia

Cada concepto aprendido debe terminar convertido en:

`
concepto → diseño → contrato → implementación → test → evidencia → documentación → integración
`

Tipos de evidencia a producir:

- ✅ Git commits públicos
- ✅ Test outputs
- ✅ Architecture diagrams
- ✅ Contracts/interfaces
- ✅ READMEs documentados
- ✅ CRIT reports
- ✅ Benchmarks comparativos
- ✅ Demos ejecutables

---

## Job Skill Matrix

Skills a desarrollar y evidenciar:

| Skill | Market Demand | Current | Implemented | Tested | Evidence | Interview Ready |
|-------|---------------|---------|-------------|--------|----------|-----------------|
| Python | Alta | ✅ | — | — | — | — |
| REST APIs | Alta | ✅ | — | — | — | — |
| LangGraph | Muy Alta | ❌ | — | — | — | — |
| MCP | Muy Alta | ❌ | — | — | — | — |
| RAG | Muy Alta | Parcial | — | — | — | — |
| ETL/Data Pipelines | Alta | ❌ | — | — | — | — |
| Metadata/Ontology | Media | ❌ | — | — | — | — |
| RDF/SPARQL/Knowledge Graphs | Alta | 🟢 | ✅ | ✅ | L10 local receipt | L10 local |
| Secure execution / sandbox | Muy Alta | 🟢 | ✅ | ✅ | L11 local receipts | L11 local |
| AWS Bedrock | Alta | ❌ | — | — | — | — |
| Testing/Evals | Muy Alta | Parcial | — | — | — | — |

*Tabla completa en JOB_SKILL_MATRIX.md*

---

## Estado Operativo Actual

`yaml
CURRENT_PHASE: L11
CURRENT_ITERATION: 1
OBJECTIVE: Governed Sandbox Layer local restricted execution
STATUS: VERIFIED (local logical sandbox scope)
BLOCKERS: AWS/OpenMetadata remoto live no autorizados o no configurados
P0: 0
P1: 0
P2: 0
NEXT_ACTION: Implementar observabilidad/evals local; después demo E2E pública y CI
`

---

## Nota de Autoría

Este laboratorio es un **entorno experimental aislado** de BAGO.

Solo las capacidades validadas aquí podrán proponerse para integración upstream en BAGO.

**Fecha de creación:** 2026-09-21
**Autor:** AMTEC_Terminal_1º
**Licencia:** MIT (pendiente confirmación)
