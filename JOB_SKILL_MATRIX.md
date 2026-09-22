# JOB SKILL MATRIX

## Vacantes Objetivo (Septiembre 2026)

### 1. Tuio — Forward Deployed AI Engineer

**Ubicación:** Remoto España/Madrid  
**Salario:** No publicado (estimado €50k-€70k)  
**Fit técnico actual:** ~96%  
**Gap principal:** Seniority (~5 años requeridos)  
**Timeline objetivo:** 4-5 semanas (completar L1-L6)

#### Requisitos vs Mi Estado

| Requisito | Estado | Evidence | Gap |
|-----------|--------|----------|-----|
| Agentes y orchestration | 🟡 En aprendizaje | — | L1 LangGraph |
| Tool calling / APIs | ✅ Conocido | BAGO backend | — |
| MCP | ✅ Baseline gobernado | mcp_adapter.py + local stdio demo + video | Tool-use cloud end-to-end |
| Bedrock provider | ✅ Baseline offline gobernado | bedrock_provider_adapter.py + 10 tests + benchmark | Live AWS validation |
| RAG | 🟡 Parcial | BAGO RAG básico | L4 |
| Validaciones/permisos | ✅ Fuerte | BAGO governance | — |
| Action limits / human escalation | ✅ Diseñado | BAGO contracts | — |
| Testing/Evals | 🟡 Parcial | Tests BAGO | Reforzar |
| Observabilidad | 🟡 Parcial | Logs BAGO | Reforzar |

---

### 2. Orbitant — AI Engineer

**Ubicación:** 100% Remoto España  
**Salario:** €40k-€60k  
**Fit técnico actual:** ~91%  
**Gaps:** LangGraph/LangChain, cloud, Docker/K8s  
**Timeline objetivo:** 2-3 semanas (completar L1-L4)

#### Requisitos vs Mi Estado

| Requisito | Estado | Evidence | Gap |
|-----------|--------|----------|-----|
| Sistemas LLM en producción | 🟡 Parcial | BAGO runtime | L1-L4 |
| Agentes y pipelines | 🟡 En diseño | — | L1-L2 |
| Python | ✅ Fuerte | BAGO backend | — |
| Evaluación de modelos | 🟡 Parcial | — | Reforzar tests |
| Orchestration frameworks | ❌ No empezado | — | L1 LangGraph |
| Vector DB | ❌ No empezado | — | L4 |
| MCP | ✅ Baseline gobernado | mcp_adapter.py + local stdio demo + video | Cloud/provider depth |
| Testing/CI-CD | 🟡 Parcial | BAGO tests | Reforzar |
| Seguridad/privacy | ✅ Fuerte | BAGO governance | — |
| Proyectos públicos | ✅ Este laboratorio | En construcción | GitHub repo |

---

### 3. Devoteam — GCP AI Engineer (Gemini Enterprise)

**Ubicación:** España (híbrido posible)  
**Salario:** No publicado  
**Fit técnico actual:** ~87% → 93% cerrando LangGraph + AWS  
**Gaps principales:** Vertex AI / GCP específico  
**Timeline objetivo:** 6-7 semanas (completar L1-L7)

#### Requisitos vs Mi Estado

| Requisito | Estado | Evidence | Gap |
|-----------|--------|----------|-----|
| Python | ✅ Fuerte | BAGO backend | — |
| LLMs | ✅ Provider baseline | Bedrock Converse/Stream offline | Live model evaluation |
| Bedrock Knowledge Bases | ✅ Baseline offline gobernado | Retrieve/Generate + citations + ETL comparison | Live KB ingestion and relevance |
| Metadata Catalog / OpenMetadata | ✅ Baseline offline gobernado | Search, lineage, ownership, schema version, quality + receipts | Live Docker deployment |
| RAG | 🟡 Parcial | — | L4 |
| LangGraph/LangChain | ❌ No empezado | — | L1 |
| Agentes | 🟡 Diseñado | BAGO agents | L1 |
| Proveedores externos | ✅ Experiencia | BAGO adapters | L6 |
| Vertex AI / Gemini | ❌ No empezado | — | Auto-study GCP |
| GCP Cloud | ❌ No empezado | — | Auto-study GCP |

**Nota:** Aunque la oferta es GCP-specific, los conceptos de Bedrock (L6-L7) son transferibles. Estudiaré GCP en paralelo tras completar L7.

---

### 4. commercetools — AI Engineer

**Ubicación:** Valencia (híbrido)  
**Salario:** No publicado  
**Fit arquitectónico:** ~97%  
**Viabilidad:** ~55% (seniority gap fuerte)  
**Timeline:** Stretch goal (aplicar tras L9 completo)

#### Requisitos vs Mi Estado

| Requisito | Estado | Evidence | Gap |
|-----------|--------|----------|-----|
| Agent loops | ✅ Diseñado | BAGO session | — |
| Tool use | ✅ Diseñado | BAGO tools | — |
| Business-rule enforcement | ✅ Fuerte | BAGO governance | — |
| Graceful failure | ✅ Diseñado | BAGO error handling | — |
| MCP seguro para APIs | ✅ Boundary implementado | Registry + effect classification + permits | Integración API real |
| Retrieval/embeddings | 🟡 Parcial | — | L4 |
| Feedback loops | 🟡 Parcial | BAGO context | Reforzar |
| Evals estructurales | ❌ No empezado | — | Reforzar tests |
| 5+ años software | ⚠️ Gap | — | Portfolio debe compensar |
| 2+ años LLM production | ⚠️ Gap | — | Este laboratorio como evidencia |

---

## Estrategia de Candidatura

### Wave 1 (2-3 semanas) — Orbitant
- Completar L0-L4
- GitHub repo público con L1-L4 evidence
- Aplicar destacando BAGO governance + RAG implementado

### Wave 2 (4-5 semanas) — Tuio
- [x] Completar L6 offline (Bedrock; L5 MCP baseline ya verificado)
- [ ] Validar L6 contra cuenta AWS real (credenciales, IAM y model access)
- Evidence de LangGraph governed execution
- Aplicar aunque seniority sea gap; portfolio como compensación

### Wave 3 (6-7 semanas) — Devoteam
- [x] Completar L7 offline (Bedrock KB + comparación ETL)
- [x] Completar L8 offline (Metadata Catalog + lineage + quality)
- [ ] Validar L7 contra Knowledge Base AWS real (ingestion, IAM, vector store, relevancia)
- [ ] Validar L8 contra OpenMetadata real (Docker, API, ownership y lineage)
- Auto-study GCP basics (transferencia desde AWS)
- Aplicar destacando adaptabilidad multi-cloud

### Wave 4 (10 semanas) — commercetools (stretch)
- [x] L9 offline completo (end-to-end governed agent)
- [x] Tres escenarios reproducibles con RAG, MCP y Bedrock fixture
- [ ] Validación live de APIs commercetools/AWS/GitHub (`NOT_RUN`)
- Aplicar como "moonshot"

---

## Skill Progress Tracker

### Technical Skills

| Skill | Market Demand | Current Level | Target Level | First Evidence | Interview Ready |
|-------|---------------|---------------|--------------|----------------|-----------------|
| Python | Alta | ✅ Senior | ✅ Senior | BAGO backend | ✅ Sí |
| REST APIs | Alta | ✅ Senior | ✅ Senior | BAGO FastAPI | ✅ Sí |
| LangGraph | Muy Alta | ❌ None | 🎯 Proficient | L1 state graph | L1 completado |
| LangChain concepts | Alta | ❌ None | 🟡 Basic | — | L1 completado |
| Multi-agent systems | Muy Alta | 🟢 Reinforced | 🎯 Proficient | GovernedKnowledgeAgent + L9 evidence | L9 offline |
| Tool use | Muy Alta | ✅ Implementado | 🎯 Proficient | BAGO tools + MCP receipts | L5 baseline |
| MCP | Muy Alta | ✅ Baseline gobernado | 🎯 Proficient | L5 MCP adapter + video | L5 baseline |
| RAG | Muy Alta | 🟡 Basic | 🎯 Advanced | L4 governed RAG | L4 completado |
| Hybrid retrieval | Alta | ❌ None | 🎯 Proficient | L4 benchmarks | L4 completado |
| Embeddings | Alta | 🟡 Conceptual | 🎯 Implementado | L4 vector store | L4 completado |
| Vector DB | Alta | ❌ None | 🎯 Proficient | L4 FAISS/Pinecone | L4 completado |
| ETL | Alta | ❌ None | 🎯 Proficient | L2 pipeline | L2 completado |
| Data pipelines | Alta | ❌ None | 🎯 Implementado | L2 end-to-end | L2 completado |
| Metadata/Ontology | Media | 🟢 Implementado | 🎯 Proficient | L3 schema + L10 engine | L10 local |
| RDF / SPARQL / Knowledge Graphs | Alta | 🟢 Baseline local | 🎯 Proficient | L10 RDF/Turtle + SPARQL + inference | L10 local; triplestore live separado |
| Lineage | Media | 🟢 Implementado | 🎯 Proficient | L3 relations + L10 paths | L10 local |
| AWS | Alta | 🟡 Adapter offline | 🎯 Bedrock fluent | L6 adapter + setup doc | Live account validation |
| Bedrock | Alta | 🟡 Provider baseline | 🎯 Proficient | L6 Converse/Stream + receipts | Live model evaluation |
| Bedrock Knowledge Bases | Alta | 🟡 Baseline offline | 🎯 Proficient | L7 Retrieve/Generate + citations | Live KB evaluation |
| OpenMetadata Catalog | Media | 🟡 Baseline offline | 🎯 Proficient | L8 adapter + lineage evidence | Live Docker evaluation |
| IAM | Alta | 🟡 Basic | 🎯 Configurable | L6 least-privilege setup | Live policy check |
| CI/CD | Alta | 🟡 Basic | 🎯 Implementado | GitHub Actions | L1 completado |
| Evaluation | Muy Alta | 🟢 Framework baseline | 🎯 Framework | 115 tests + README/L9/L10 scenarios | L10 offline |
| Observability | Alta | 🟢 Reinforced | 🎯 Completo | Receipts + evidence links + ontology receipt | L10 offline |
| Secure execution | Muy Alta | ✅ Diseñado | 🎯 Implementado | BAGO auth boundary | L1 completado |
| Authorization | Muy Alta | ✅ Diseñado | 🎯 Implementado | BAGO permits | L1 completado |
| Auditability | Alta | ✅ Diseñado | 🎯 Implementado | BAGO receipts | L1 completado |
| Docker/K8s | Media | ❌ None | 🟡 Basic | Docker Compose | L2/L7 |

### Soft Skills / Strategic

| Skill | Current | Target | Evidence |
|-------|---------|--------|----------|
| Arquitectura de sistemas | ✅ Fuerte | ✅ Mantener | AGENTS.md, CANON_BAGO |
| Diseño de contratos | ✅ Fuerte | ✅ Mantener | BAGO contracts |
| Documentación técnica | ✅ Fuerte | ✅ Mantener | Este repo |
| Análisis de trade-offs | ✅ Fuerte | ✅ Mantener | Decision records |
| Comunicación escrita | ✅ Fuerte | ✅ Mantener | Docs claras |

---

## Evidence Checklist por Candidatura

### Para Orbitant (L0-L4)

- [ ] README.md con propósito del proyecto
- [ ] ARCHITECTURE.md con diagramas
- [ ] L1: LangGraph state graph funcionando + tests
- [ ] L2: ETL pipeline ingestando docs BAGO
- [ ] L3: Metadata schema + ontología
- [ ] L4: RAG gobernado con benchmarks FTS vs embeddings vs hybrid
- [ ] LEARNING_LEDGER.md con entradas de L1-L4
- [ ] GitHub commits verdes (actividad visible)

### Para Tuio (añadir L5-L6)

- [x] L5: MCP adapter + server local demo + video
- [x] L6: Bedrock provider adapter funcionando offline con permits y receipts
- [x] Evidence de authorization boundary en acción (10 tests + benchmark)
- [ ] Receipts de ejecuciones reales (AWS live `NOT_RUN`)
- [ ] L6: benchmark de latencia/precio cloud
- [ ] CRIT report mostrando tests de gobernanza

### Para Devoteam (añadir L7-L8 + GCP study)

- [x] L7: Bedrock KB adapter funcionando offline con permits y citations
- [x] Comparativa BAGO ETL vs Bedrock KB sobre la misma query (fixture)
- [x] L8: OpenMetadata-shaped catalog adapter con lineage, ownership, versionado y quality rules
- [x] Evidencia L8 con source → asset → chunk y receipts gobernados (fixture)
- [ ] L7: Knowledge Base AWS real, ingestion y benchmark de relevancia
- [ ] L8: OpenMetadata real con Docker y API
- [ ] Auto-study notes de GCP (Vertex AI, Gemini)
- [ ] Transferencia explícita AWS → GCP en docs

### Para commercetools (L9 completo)

- [x] End-to-end agent funcionando offline
- [x] 3 scenarios de demo reproducibles en Markdown
- [ ] Video nuevo de las 3 demos (`NOT_RUN`)
- [ ] Portfolio máximo: L0-L9 todo VALIDATED
- [ ] Cover letter explicando architecture fit 97%

---

## Tracking Semanal

### Semana 1 (2026-09-21 → 2026-09-28)

**Objetivo:** L0 completo + L1 iniciado  
**Completado:**
- [ ] LAB_CONTRACT.md
- [ ] ARCHITECTURE.md
- [ ] ROADMAP.md
- [ ] LEARNING_LEDGER.md
- [ ] JOB_SKILL_MATRIX.md (este documento)
- [ ] GitHub repo inicializado
- [ ] L1 implementado (state graph)

**Bloqueos:** Ninguno esperado  
**Horas estimadas:** 10-15h

---

**Última actualización:** 2026-09-22
**Próxima revisión:** 2026-09-28 (fin semana 1)
