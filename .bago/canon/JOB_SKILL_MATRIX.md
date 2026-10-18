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
| Agentes y orchestration | L1 local validated | StateGraph + GovernedRAG + Gateway/Sandbox + LocalTrace | production identity and durable runtime remain separate |
| Tool calling / APIs | ✅ Conocido | BAGO backend | — |
| MCP | ✅ Baseline gobernado | mcp_adapter.py + local stdio demo + video | Tool-use cloud end-to-end |
| Bedrock provider | 🟡 Converse live histórico; últimos dos intentos limitados por cuota diaria | adapter + tests + benchmark + recibos live y Free Tier | Recuperar cuota, validar Stream e IAM least-privilege; facturación actual no probada |
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
| Orchestration frameworks | LangGraph implemented locally | L1 interrupt/resume, exact approval, receipts and tests | cloud/runtime depth remains separate |
| Vector DB | 🟢 Local persistente | SQLiteVectorStore + GovernedRAG | L14 |
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
| Metadata Catalog / OpenMetadata | ✅ Adapter + local live verificado | Search, lineage, ownership, schema version, quality + receipts contra Docker local | OpenMetadata remoto |
| RAG | 🟡 Parcial | — | L4 |
| LangGraph/LangChain | LangGraph local baseline validated | StateGraph + interrupt/resume + governed execution evidence | managed checkpoint and cloud model integration remain separate |
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
- [x] Validar L6 `Converse` contra cuenta AWS real (credenciales, model access y receipt)
- [x] Confirmar cuenta AWS `FREE/ACTIVE` y créditos restantes mediante API Free Tier de solo lectura
- [ ] Validar L6 `ConverseStream` y política IAM least-privilege
- Evidence de LangGraph governed execution
- Aplicar aunque seniority sea gap; portfolio como compensación

### Wave 3 (6-7 semanas) — Devoteam
- [x] Completar L7 offline (Bedrock KB + comparación ETL)
- [x] Completar L8 offline (Metadata Catalog + lineage + quality)
- [x] Ejecutar L8 live local contra OpenMetadata Docker con cleanup y receipts
- [ ] Validar L7 contra Knowledge Base AWS real (ingestion, IAM, vector store, relevancia)
- [ ] Validar L8 contra OpenMetadata remoto (la validación Docker local ya está verificada)
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

**Matrix convention:** Market demand uses Muy alta, Alta and Media. Current-level colors describe evidence maturity: 🟢 implemented or evidenced locally; 🟡 practical baseline, partial evidence or bounded scope; 🟠 historical evidence or external constraint; 🔵 designed capability without an implementation claim. 🎯 marks the target level. Colors describe evidence scope, not professional proficiency. The final column records evidence scope and remaining limits.

| Skill | Market Demand | Current Level | Target Level | First Evidence | Interview Ready |
|-------|---------------|---------------|--------------|----------------|-----------------|
| Python | Alta | 🟢 Senior | 🎯 Senior | BAGO backend | ✅ Sí |
| REST APIs | Alta | 🟢 Senior | 🎯 Senior | BAGO FastAPI | ✅ Sí |
| LangGraph | Muy alta | 🟢 Implementado localmente | 🎯 Proficient | Integrated StateGraph + exact approval + governed RAG/gateway/sandbox/receipt/LocalTrace | L1 VALIDATED in local scope; identity, durability and OS isolation are not claimed |
| LangChain concepts | Alta | 🟡 Baseline práctico | 🎯 Basic | StateGraph, interrupt/resume, in-memory checkpoint | L1 VALIDATED in local scope; checkpoint is in-memory |
| Multi-agent systems | Muy alta | 🟢 Reinforced | 🎯 Proficient | GovernedKnowledgeAgent + L9 evidence | L9 offline |
| Tool use | Muy alta | 🟢 Implementado | 🎯 Proficient | BAGO tools + MCP receipts | L5 baseline |
| MCP | Muy alta | 🟡 Baseline gobernado | 🎯 Proficient | L5 MCP adapter + video | L5 baseline |
| RAG | Muy alta | 🟡 Basic | 🎯 Advanced | L4 governed RAG | L4 completado |
| Hybrid retrieval | Alta | 🟡 Implemented locally; deterministic benchmark is limited | 🎯 Proficient | 32-document offline corpus; 9 labelled queries; Recall@1/@3 and MRR | Synthetic baseline only; production embeddings and broader relevance validation remain |
| Embeddings | Alta | 🟡 Deterministic local | 🎯 Implementado | HashEmbedding + SQLiteVectorStore | L14 local |
| Vector DB | Alta | 🟢 Local persistent | 🎯 Proficient | SQLiteVectorStore + GovernedRAG reload | L14 local; distributed service separate |
| ETL | Alta | 🟡 Implemented locally; coverage partial | 🎯 Proficient | L2 source-to-SQLite pipeline; deduplication, receipts and enforced chunk-overlap test | Local pipeline verified; partial-failure and transaction recovery coverage remains |
| Data pipelines | Alta | 🟡 Implemented locally; local/document scope | 🎯 Implementado | L2 ingestion consumed by L4 SQLite retrieval adapter | No evidence yet for scheduled recovery or distributed processing |
| Metadata/Ontology | Media | 🟢 Implementado | 🎯 Proficient | L3 schema + L10 engine | L10 local |
| RDF / SPARQL / Knowledge Graphs | Alta | 🟡 Baseline local | 🎯 Proficient | L10 RDF/Turtle + SPARQL + inference | L10 local; triplestore live separado |
| Lineage | Media | 🟢 Implementado | 🎯 Proficient | L3 relations + L10 paths | L10 local |
| AWS | Alta | 🟠 Bedrock Converse live histórico; cuota diaria agotada en los últimos intentos | 🎯 Bedrock fluent | L6 adapter + receipt live + consulta Free Tier | IAM least-privilege + recuperar cuota; saldo/cargo posterior no probado |
| Bedrock | Alta | 🟠 Converse histórico verificado; intentos actuales limitados por cuota | 🎯 Proficient | L6 Converse/Stream + receipts | Stream + evaluación de modelo y cuota disponible |
| Bedrock Knowledge Bases | Alta | 🟡 Baseline offline | 🎯 Proficient | L7 Retrieve/Generate + citations | Live KB evaluation |
| OpenMetadata Catalog | Media | 🟢 Local live verificado | 🎯 Proficient | L8 adapter + Docker local + lineage/quality receipts | OpenMetadata remoto |
| IAM | Alta | 🟡 Basic | 🎯 Configurable | L6 least-privilege setup | Live policy check |
| CI/CD | Alta | 🟢 Reproducible | 🎯 Implementado | GitHub Actions + pinned requirements + public E2E | L13 CI |
| Evaluation | Muy alta | 🟢 Local governance evals | 🎯 Framework | Local evaluation suites, trace/evidence linkage, and L8-L15 scenario evidence | L15 local + CI |
| Observability | Alta | 🟢 OpenTelemetry local live | 🎯 Completo | LocalTrace + OTLP/HTTP + Jaeger Docker + parent-linked spans | L15 local; remoto separado |
| Secure execution | Muy alta | 🟢 Local backend verified | 🎯 Implementado | BAGO auth boundary + LocalRestrictedBackend + escape tests | L11 local |
| Authorization | Muy alta | 🔵 Diseñado | 🎯 Implementado | L1 fail-closed gate; MCP, Bedrock y sandbox tienen límites probados por separado | L1 evidencia parcial |
| Auditability | Alta | 🔵 Diseñado | 🎯 Implementado | Recibos de adapters/sandbox; L1 no fabrica recibos si no hay gateway | L1 evidencia parcial |
| Docker/K8s | Media | 🟡 Docker Compose local | 🎯 Basic | OpenMetadata Compose + reproducible healthcheck | L8 local |



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
- [ ] .bago/canon/ARCHITECTURE.md con diagramas
- [ ] L1: LangGraph state graph funcionando + tests
- [ ] L2: ETL pipeline ingestando docs BAGO
- [ ] L3: Metadata schema + ontología
- [ ] L4: RAG gobernado con benchmarks FTS vs embeddings vs hybrid
- [ ] .bago/canon/LEARNING_LEDGER.md con entradas de L1-L4
- [ ] GitHub commits verdes (actividad visible)

### Para Tuio (añadir L5-L6)

- [x] L5: MCP adapter + server local demo + video
- [x] L6: Bedrock provider adapter funcionando offline con permits y receipts
- [x] Evidence de authorization boundary en acción (10 tests + benchmark)
- [x] Receipt de una ejecución real AWS `Converse`
- [x] Receipt de cobertura de cuenta Free Tier (sin invocar Cost Explorer)
- [ ] Receipt de `ConverseStream` con cuota autorizada y reconciliación posterior de consumo/facturación
- [ ] L6: benchmark de latencia/precio cloud
- [ ] CRIT report mostrando tests de gobernanza

### Para Devoteam (añadir L7-L8 + GCP study)

- [x] L7: Bedrock KB adapter funcionando offline con permits y citations
- [x] Comparativa BAGO ETL vs Bedrock KB sobre la misma query (fixture)
- [x] L8: OpenMetadata-shaped catalog adapter con lineage, ownership, versionado y quality rules
- [x] Evidencia L8 con source → asset → chunk y receipts gobernados (fixture)
- [x] L8 live local con Docker, API, lineage, ownership, schema, quality y cleanup
- [ ] L7: Knowledge Base AWS real, ingestion y benchmark de relevancia
- [ ] L8: OpenMetadata remoto con credenciales propias
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
- [ ] .bago/canon/LAB_CONTRACT.md
- [ ] .bago/canon/ARCHITECTURE.md
- [ ] .bago/canon/ROADMAP.md
- [ ] .bago/canon/LEARNING_LEDGER.md
- [ ] .bago/canon/JOB_SKILL_MATRIX.md (este documento)
- [ ] GitHub repo inicializado
- [ ] L1 implementado (state graph)

**Bloqueos:** Ninguno esperado  
**Horas estimadas:** 10-15h

---

**Última actualización:** 2026-09-22
**Próxima revisión:** 2026-09-28 (fin semana 1)

## Portfolio Evidence Update — 2026-10-10 (isolated candidate)

Target profile: **AI platform and agent engineering**. This candidate adds a repeatable Agent Evaluation Lab and trace-linked real-provider evaluation, addressing the project's prior gap between governance checks and answer-level regression checks. It remains an uncommitted worktree change, not an integrated release.

- **Agent evaluation:** `EXECUTED` in `codex/adl-agent-evaluation-lab-20261010`; versioned suites, deterministic declared checks, preflighted Ollama inference, immutable run history, model/agent fingerprint and LocalTrace.
- **Real provider evidence:** one synthetic single-turn run with `gemma4:31b` and the persisted ADL Read Evidence Agent returned the requested token; result `PASS`. See `.bago/goals/ADL-AGENT-EVALUATION-LAB-001/evidence/live-ollama/receipt.json`. This is a pipeline smoke test, not evidence of general agent quality.
- **Checks:** backend 27 passed; frontend API 5 passed; rendered initial-loading smoke 1 passed; TypeScript/Vite production build passed. Full UI state coverage remains incomplete; lint and Jaeger export are `NOT_RUN`.
- **Market context:** LangChain's 2026 survey reports quality as a leading production barrier and offline evaluations in use among surveyed teams; Dynatrace's 2026 SRE report highlights model performance/accuracy monitoring and observability/governance. These reports inform the portfolio prioritization; they do not establish hiring outcomes.
  - [LangChain State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering?trk=article-ssr-frontend-pulse_little-text-block)
  - [Dynatrace State of SRE Report 2026](https://www.dynatrace.com/resources/ebooks/sre-report/)
