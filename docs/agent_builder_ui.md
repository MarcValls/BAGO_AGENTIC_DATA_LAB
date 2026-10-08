# BAGO Frontend de Orquestación y Agent Builder

Dashboard interactivo con control de ejecución de demos y wizard asistido para crear agentes.

## Características Nuevas

### 🎮 Control Panel
- Ejecutar `python demo.py` desde la UI
- Logs en tiempo real (WebSocket o HTTP polling)
- Opciones: escribir evidence bundle, salida JSON
- Descarga de logs
- Estado de ejecución en tiempo real

### 🤖 Agent Builder Wizard
Asistente paso a paso para crear agentes:
1. **Seleccionar**: elegir template o crear custom
2. **Configurar**: nombre, descripción, tipo, prompt, herramientas
3. **Preview**: revisar configuración
4. **Guardar**: persistencia en `agents/created/`

**Templates incluidos:**
- RAG Basic — retrieval + Bedrock
- Multi-Tool — múltiples herramientas con orquestación
- Governed Retrieval — RAG con autorización y sandbox

**Configuración por agente:**
- Tipo: RAG / Tool / Multi-Agent
- Herramientas: Bedrock, MCP, Ontology, Retrieval, Sandbox
- Retrieval: modo hybrid/semantic/lexical, top-k
- Sandbox: perfiles de seguridad (test_runner, restricted, isolated)

## Endpoints API Nuevos

### Demo Orchestration
```
POST   /api/demo/run              — ejecutar demo (HTTP)
WS     /ws/demo/run               — ejecutar demo (WebSocket streaming)
GET    /api/demo/status           — estado del demo
```

### Agent Management
```
POST   /api/agents/create         — crear nuevo agente
GET    /api/agents/list           — listar todos los agentes
GET    /api/agents/{agent_id}     — obtener un agente específico
```

## Stack

**Frontend:**
- React 18 + TypeScript + Vite
- Componentes: Control, AgentBuilder, Summary, Retrieval, Authorization, Trace, Evaluation
- WebSocket para logs en tiempo real
- Wizard pattern con multi-step UI

**Backend:**
- FastAPI + Uvicorn
- WebSocket support para streaming
- Persistencia en `agents/created/` (JSON)
- CORS habilitado

## Uso

### Local
```bash
# Generar artifacts
python demo.py

# Instalar deps
pip install -r requirements.txt fastapi uvicorn
cd frontend && npm install && npm run build

# Ejecutar
python -m src.api.server
# http://localhost:8080
```

### Docker Compose
```bash
python demo.py  # generar artifacts primero
docker compose -f docker-compose.ui.yml up -d
# http://localhost:8080
# Jaeger: http://localhost:16687
```

## Flujo Completo

1. **Abrir Dashboard** → `http://localhost:8080`
2. **Tab Agent Builder**:
   - Seleccionar template o crear custom
   - Configurar nombre, herramientas, prompts
   - Preview y guardar
3. **Tab Control**:
   - Ejecutar demo con opciones
   - Ver logs en tiempo real
   - Descargar o limpiar logs
4. **Tabs Análisis**:
   - Summary: métricas globales
   - Retrieval: chunks y ontología
   - Authorization: permisos y receipts
   - Trace: timeline de eventos
   - Evaluation: governance checks

## Estructura de Archivos

```
frontend/src/components/
├── Control.tsx           # Demo execution + live logs
├── Control.css
├── AgentBuilder.tsx      # Multi-step wizard
├── AgentBuilder.css
├── Summary.tsx           # Métricas
├── Retrieval.tsx         # RAG + ontología
├── Authorization.tsx     # Permisos
├── Trace.tsx             # Timeline
└── Evaluation.tsx        # Governance

src/api/
└── server.py             # FastAPI endpoints

agents/created/           # Agentes guardados (JSON)
```

## Persistencia de Agentes

Los agentes se guardan en:
```
agents/created/{agent_id}.json
```

Formato:
```json
{
  "id": "agent_12345678",
  "config": {
    "name": "My Agent",
    "description": "...",
    "type": "rag",
    "system_prompt": "...",
    "tools": ["retrieval.search", "bedrock.converse"],
    "retrieval_config": {"mode": "hybrid", "top_k": 5},
    "sandbox_profile": "test_runner"
  },
  "created_at": "2026-10-03T07:30:00.000000"
}
```

## Próximos Pasos

- [ ] Ejecutar agentes creados desde Control panel
- [ ] Historial de ejecuciones (jobs) con duración/status
- [ ] Export/import agentes
- [ ] Versioning de agentes
- [ ] Integración con CI/CD — disparar workflows
- [ ] Métricas de performance de agentes
