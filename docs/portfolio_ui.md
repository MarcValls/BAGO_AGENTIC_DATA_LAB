# BAGO Portfolio UI — React Dashboard

Dashboard web interactivo para visualizar los artefactos de la demo BAGO Governed Knowledge Agent.

## Características

- **Summary**: métricas de estado, costo, tests, ontología y sandbox
- **Retrieval & Ontology**: hits recuperados, pipelines, paths RDF/SPARQL, triples inferidos
- **Authorization**: tool proposals, permits, provider receipts (Bedrock), sandbox execution
- **Trace**: timeline de eventos, evidence references, estadísticas
- **Evaluation**: checks de gobernanza, score, interpretación

## Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Backend API**: FastAPI + Uvicorn
- **Styling**: CSS puro (dark theme)
- **Packaging**: Docker multi-stage (Node + Python)

## Uso

### Desarrollo local

```bash
# Instalar deps frontend
cd frontend
npm install
npm run build

# Instalar deps backend
pip install -r requirements.txt fastapi uvicorn

# Generar demo artifacts (si no existen)
python demo.py

# Ejecutar API
python -m src.api.server
# -> http://localhost:8080
```

### Docker Compose

```bash
# Generar artifacts primero
python demo.py

# Levantar API + UI + Jaeger (opcional)
docker compose -f docker-compose.ui.yml up -d

# Acceder
# - Dashboard: http://localhost:8080
# - Jaeger: http://localhost:16686
```

### Docker solo

```bash
docker build -f Dockerfile.ui -t bago-portfolio:latest .
docker run -p 8080:8080 -v ./demo_output/latest:/app/demo_output/latest:ro bago-portfolio:latest
```

## Estructura

```
frontend/
├── src/
│   ├── main.tsx              # React entry point
│   ├── App.tsx               # Main component + tab switching
│   ├── index.css             # Global styles (dark theme)
│   └── components/
│       ├── Summary.tsx       # Overview metrics
│       ├── Retrieval.tsx     # RAG + ontology engine
│       ├── Authorization.tsx # Permits + receipts
│       ├── Trace.tsx         # Event timeline
│       └── Evaluation.tsx    # Governance checks
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts

src/api/
└── server.py                 # FastAPI endpoints
    - GET /api/artifacts
    - GET /api/summary
    - GET /api/agent-run
    - GET /api/receipts
    - GET /api/trace
    - GET /api/evaluation
    - GET /api/health
```

## API Endpoints

Todos los endpoints retornan JSON desde `demo_output/latest/`:

| Endpoint | Retorna |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/artifacts` | Objeto con todas las artefactos |
| `GET /api/summary` | Métricas de alto nivel |
| `GET /api/agent-run` | Query, respuesta, citations, proposals |
| `GET /api/receipts` | Permisos, provider, sandbox |
| `GET /api/trace` | Timeline de eventos |
| `GET /api/evaluation` | Checks de gobernanza y score |

## Configuración

La ruta de artifacts se define en `src/api/server.py`:

```python
DEMO_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "demo_output" / "latest"
FRONTEND_BUILD = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
```

Modifica si los artifacts están en otra ubicación.

## Notas

- La UI es **read-only**: sólo consume artifacts existentes
- Requiere que `python demo.py` haya sido ejecutado antes
- El frontend se sirve estáticamente desde `frontend/dist/`
- CORS habilitado en `*` para desarrollo; restricciones en producción según sea necesario
