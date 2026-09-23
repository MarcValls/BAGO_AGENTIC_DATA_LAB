# L15 · OpenTelemetry + Jaeger local

L15 proyecta el `LocalTrace` ya construido por BAGO a spans OpenTelemetry y
los envía a Jaeger en Docker mediante OTLP/HTTP.

```text
AgentRun + receipts + sandbox
  → LocalTraceBuilder
  → OpenTelemetry spans con parent links
  → OTLP/HTTP :4318
  → Jaeger local
  → query API :16686
  → evidencia L15
```

## Reproducir

Dependencias Python y Docker Compose son las únicas piezas necesarias:

```bash
python -m pip install -r requirements.txt
docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check
python scripts/run_l15_otel_live_validation.py --write-evidence
docker compose -p bago-otel -f infra/observability/docker-compose.yml down
```

La UI queda disponible en `http://localhost:16686`. El exporter usa
`http://localhost:4318/v1/traces` y el servicio se identifica como
`bago-agentic-data-lab`.

## Contrato de gobernanza

`LocalTrace` sigue siendo la fuente de evidencia. `otel_bridge.py` sólo
proyecta eventos ya producidos; no decide permisos, no ejecuta capacidades y
no sustituye receipts ni evaluaciones. Si el exporter falla, la validación
queda en `FAILURE` y no se presenta como observabilidad live.

## Alcance

La prueba usa el E2E público y un Jaeger all-in-one local fijado a `1.60.0`.
Demuestra exportación OTLP, relaciones parent/child, consulta y presencia de
operaciones gobernadas. No demuestra producción, alta disponibilidad, retención
durable, AWS, SaaS ni un collector remoto; esas superficies siguen `NOT_RUN`.
