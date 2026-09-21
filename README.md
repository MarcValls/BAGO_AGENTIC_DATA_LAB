# 🧪 BAGO Agentic Data Lab

[![GitHub](https://img.shields.io/badge/GitHub-Repo-blue)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)
[![Branch](https://img.shields.io/badge/branch-main-green)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/tree/main)
[![Commits](https://img.shields.io/badge/commits-5-orange)](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/commits/main)
[![Tests](https://img.shields.io/badge/tests-11/11 ✅-brightgreen)]()
[![Chunks](https://img.shields.io/badge/chunks_indexed-65-purple)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> **Laboratorio experimental para desarrollar capacidades de AI Engineering con gobernanza BAGO**
> 
> Última actualización: 2026-09-21 21:13:03

---

## 📊 Estado Actual

| Métrica | Valor |
|---------|-------|
| **Último Commit** | L2: ETL Pipeline VALIDATED |
| **Tests Passing** | 11/11 ✅ |
| **Chunks Indexados** | 65 (3 docs) |
| **Fase Actual** | L2 ✅ COMPLETE |
| **Próxima Fase** | L3 · Metadata & Ontology |

---

## 🗺️ Roadmap

`mermaid
gantt
    title BAGO Agentic Data Lab - Roadmap
    dateFormat  YYYY-MM-DD
    
    section Completed
    L0: Baseline           :done, 2026-09-21, 1d
    L1: LangGraph          :done, 2026-09-21, 1d
    L2: ETL Pipeline       :done, 2026-09-21, 1d
    
    section Next
    L3: Metadata           :active, 2026-09-28, 7d
    
    section Pending
    L4: Governed RAG       :crit, after L3, 7d
    L5: MCP                :crit, after L4, 7d
    L6: AWS Bedrock        :crit, after L5, 7d
    L9: End-to-End Agent   :crit, after L8, 7d
`

### Fases

| Fase | Estado | Descripción | Job Target |
|------|--------|-------------|------------|
| L0 | ✅ | Baseline & Lab Contract | - |
| L1 | ✅ | LangGraph Governed Execution | - |
| L2 | ✅ | ETL Pipeline (idempotencia, receipts) | - |
| L3 | ⏳ | Metadata & Ontology | - |
| L4 | ⏳ | Governed RAG | **Orbitant** |
| L5 | ⏳ | MCP | **Tuio** |
| L6 | ⏳ | AWS Bedrock | **Tuio** |
| L9 | ⏳ | End-to-End Agent | **commercetools** |

---

## 🏗️ Arquitectura

**Principio:** LangGraph propone → BAGO autoriza → ExecutionGateway ejecuta → Receipt evidencia

`
┌──────────────────────────────────────┐
│     BAGO GOVERNANCE LAYER            │
│  AuthorizationBoundary → Permit      │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│   LANGGRAPH ORCHESTRATION            │
│  START → classify → retrieve → ...   │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│   CAPABILITY ADAPTERS                │
│  ETL | RAG | MCP | Bedrock | APIs    │
└──────────────────────────────────────┘
`

---

## 📁 Estructura

`
BAGO_AGENTIC_DATA_LAB/
├── src/
│   ├── orchestration/state_graph.py  # L1 ✅
│   ├── etl/pipeline.py               # L2 ✅
│   ├── retrieval/                    # L4 ⏳
│   └── metadata/                     # L3 ⏳
├── tests/
│   ├── test_l1_governance.py         # 7 tests ✅
│   └── test_l2_etl_pipeline.py       # 4 tests ✅
├── l2_etl_metadata.db                # 65 chunks
├── LAB_CONTRACT.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── LEARNING_LEDGER.md
├── JOB_SKILL_MATRIX.md
├── STATE.md
└── README.md                         # Este archivo (dinámico)
`

---

## 🎯 Job Market

| Empresa | Rol | Fit | Gap | Wave |
|---------|-----|-----|-----|------|
| Orbitant | AI Engineer | 93% | RAG + Cloud | 2-3 sem |
| Tuio | Forward Deployed AI | 97% | MCP + Bedrock | 4-5 sem |
| Devoteam | GCP AI Engineer | 89% | Vertex AI | 6-7 sem |
| commercetools | AI Engineer | 97% | Portfolio | 10 sem |

### Skills Evidenciadas

✅ Python, pytest, CRIT P0  
✅ ETL, idempotencia, content hashing  
✅ Receipts y observabilidad  
✅ LangGraph StateGraph  
✅ Gobernanza BAGO  

⏳ En progreso: Metadata, RAG, MCP, Bedrock

---

## 🔧 Comandos

`ash
# Tests
python -m pytest tests/ -v

# Ver chunks
python -c "from src.etl.pipeline import ETLPipeline; p=ETLPipeline(); print(f'DB: {p.db_path}')"

# Regenerar este README
python scripts/generate_dynamic_readme.py
`

---

**Nota:** README generado dinámicamente. Métricas reflejan estado real del repo.

Generado: 2026-09-21 21:13:03
