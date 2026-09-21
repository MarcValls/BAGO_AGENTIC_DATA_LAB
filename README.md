# BAGO AGENTIC DATA LAB

**Estado:** L0 — Baseline & Lab Contract  
**Inicio:** 2026-09-21  
**Objetivo:** Portfolio público de AI Engineering para oportunidades laborales

---

## Propósito

Laboratorio experimental para desarrollar **evidencia técnica verificable** en tecnologías de AI Engineering demandadas por el mercado, integradas con la arquitectura gobernada de BAGO.

No es académico. Es **empleabilidad mediante ejecución técnica**.

---

## Vacantes Objetivo

| Empresa | Rol | Fit Técnico | Timeline | Prioridad |
|---------|-----|-------------|----------|-----------|
| **Orbitant** | AI Engineer | ~91% | 2-3 semanas | 🎯 Wave 1 |
| **Tuio** | Forward Deployed AI Engineer | ~96% | 4-5 semanas | 🎯 Wave 2 |
| **Devoteam** | GCP AI Engineer | ~87%→93% | 6-7 semanas | 🎯 Wave 3 |
| **commercetools** | AI Engineer | ~97% | 10 semanas | Stretch |

---

## Roadmap (L0 → L9)

`
L0 · Baseline & Contract      [EN PROGRESO]  2026-09-21
L1 · LangGraph Execution      [PENDIENTE]    2026-09-28
L2 · ETL Pipeline             [PENDIENTE]    2026-10-05
L3 · Metadata & Ontology      [PENDIENTE]    2026-10-12
L4 · Governed RAG             [PENDIENTE]    2026-10-19
L5 · MCP                      [PENDIENTE]    2026-10-26  ← Candidatura Orbitant
L6 · AWS Bedrock              [PENDIENTE]    2026-11-02  ← Candidatura Tuio
L7 · Bedrock Knowledge Base   [PENDIENTE]    2026-11-09  ← Candidatura Devoteam
L8 · Metadata Catalog         [PENDIENTE]    2026-11-16
L9 · End-to-End Agent         [PENDIENTE]    2026-12-01  ← Portfolio completo
`

---

## Arquitectura Clave

**Principio fundamental:** BAGO gobierna. Las tecnologías externas implementan capacidades.

`
LangGraph (orchestration)
    ↓
Reasoning Layer
    ↓
Authorization Boundary ← BAGO GOVERNANCE
    ↓
Execution Gateway
    ↓
External Capabilities (Bedrock, MCP, APIs, Vector DBs)
`

**Regla crítica:** Ningún framework externo ejecuta efectos materiales directamente sin autorización explícita de BAGO.

---

## Documentos Fundacionales

- 📄 [LAB_CONTRACT.md](./LAB_CONTRACT.md) — Propósito, inteligencia de mercado, principios
- 📐 [ARCHITECTURE.md](./ARCHITECTURE.md) — Diseño arquitectónico completo
- 🗺️ [ROADMAP.md](./ROADMAP.md) — Roadmap ejecutivo L0-L9
- 📚 [LEARNING_LEDGER.md](./LEARNING_LEDGER.md) — Registro de aprendizaje por fase
- 💼 [JOB_SKILL_MATRIX.md](./JOB_SKILL_MATRIX.md) — Skills requeridas vs estado actual

---

## Estado Operativo

`yaml
Fase_actual: L0
Completado: 20%
Bloqueos: Ninguno
P0_issues: 0
P1_issues: 0
Tests_passing: 0/0
Evidence_generada: 4 docs
Next_action: Inicializar repo GitHub + comenzar L1
`

---

## Licencia

MIT License (pendiente confirmación)

---

**Última actualización:** 2026-09-21  
**Contacto:** AMTEC_Terminal_1º
