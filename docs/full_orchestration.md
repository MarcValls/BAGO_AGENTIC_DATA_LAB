# BAGO Frontend: Full Orchestration Suite

Dashboard completo con control, agent builder, job history y análisis de demos.

## Componentes Implementados

### 1. 🤖 Agent Builder (Wizard)
- **Seleccionar**: 3 templates listos + custom
- **Configurar**: nombre, descripción, tipo, prompt, herramientas, retrieval, sandbox
- **Preview**: revisar antes de guardar
- **Guardar**: persistencia en `agents/created/` (JSON)

**Templates:**
- RAG Basic — retrieval + Bedrock
- Multi-Tool — múltiples herramientas
- Governed Retrieval — RAG + sandbox

### 2. 🚀 Control Panel
- Ejecutar demo desde UI
- **WebSocket** para logs en tiempo real
- **HTTP** fallback si WebSocket falla
- Opciones: evidence bundle, JSON output
- Descarga/limpieza de logs
- Status indicator (running/success/error/timeout)

### 3. 📊 Job History
- Tabla filtrable (all/demo/agent)
- Status indicators con emojis
- Duración, costo, exit code
- Panel detallado al seleccionar job
- Logs en paneles separados (stdout/stderr)
- Auto-refresh cada 5s
- Métricas por job

### 4. 📈 Análisis Tabs
- **Summary**: métricas globales
- **Retrieval**: chunks, pipeline, ontología, SPARQL
- **Authorization**: permits, receipts, sandbox
- **Trace**: timeline de eventos con evidence
- **Evaluation**: checks de gobernanza, score

## API Endpoints Nuevos

### Job Management
```
GET    /api/jobs/list                      — listar trabajos (con filtro limit)
GET    /api/jobs/{job_id}                  — obtener job específico
GET    /api/agents/{agent_id}/metrics      — métricas agregadas del agente
```

### Ejecución Mejorada
```
POST   /api/demo/run                       — ejecutar demo (HTTP, con job tracking)
WS     /ws/demo/run                        — ejecutar demo (WebSocket streaming + job)
```

## Estructura de Job

```python
JobExecution {
  job_id: str              # job_<uuid>
  agent_id: str | None     # None para demo runs
  job_type: str            # 'demo' | 'agent'
  status: str              # 'running' | 'success' | 'failed' | 'timeout'
  created_at: str          # ISO datetime
  completed_at: str | None # ISO datetime
  duration_ms: int | None  # milisegundos
  exit_code: int | None    # return code del proceso
  stdout: str              # últimos 1000 chars
  stderr: str              # últimos 1000 chars
  cost_usd: float          # costo total
  metrics: dict | None     # retrieval hits, ontology paths, etc.
}
```

Almacenado en: `jobs/history/{job_id}.json`

## Métricas de Agente

```python
get_agent_metrics(agent_id) → {
  agent_id: str
  total_runs: int          # total de ejecuciones
  successful_runs: int     # ejecuciones exitosas
  failed_runs: int         # ejecuciones fallidas
  success_rate: float      # 0.0-1.0
  avg_duration_ms: int     # duración promedio
  total_cost_usd: float    # costo acumulado
}
```

## Flujo End-to-End

1. **Agent Builder** → Crear agente "Customer Support"
2. **Control** → Ejecutar demo, ver logs en vivo
3. **Job History** → Seleccionar último job, ver detalle
4. **Summary** → Ver métricas globales
5. **Retrieval** → Ver chunks recuperados
6. **Trace** → Timeline de eventos
7. **Evaluation** → Checks de gobernanza PASS

## Frontend Tabs

```
🤖 Agent Builder    → Wizard 4-step para crear agentes
🚀 Control          → Ejecutar demo + logs
📊 Job History      → Tabla de trabajos + detalle
📈 Summary          → Métricas
📊 Retrieval        → Chunks + ontología
🔒 Authorization    → Permisos + receipts
⏱️ Trace            → Timeline de eventos
✅ Evaluation       → Governance checks
```

## Persistencia

```
agents/created/
├── agent_<hash>.json
└── agent_<hash>.json

jobs/history/
├── job_<uuid>.json
├── job_<uuid>.json
└── job_<uuid>.json
```

## Performance Optimizations

- Job list capped at 50 items (configurable)
- Auto-refresh cada 5s (sin hammer al servidor)
- Logs truncados a 1000 chars en storage
- Métricas agregadas on-demand (no precalculadas)

## Próximos Pasos (Ya Implementados)

✅ Job History con tabla y detalle
✅ Tracking de ejecuciones (demo + agentes)
✅ Métricas por agente
✅ Status indicators y timestamps
✅ Logs capturados y persistidos

## Aún Pendiente

- [ ] Ejecutar agentes creados (necesita scheduler)
- [ ] Export/import agentes (botones en wizard)
- [ ] CI/CD trigger desde UI (GitHub Actions integration)
- [ ] Gráficos de performance (Chart.js)
- [ ] Alertas en fallos
- [ ] WebSocket ping/pong heartbeat
