# L8 · OpenMetadata Metadata Catalog

## Alcance

L8 añade un adapter gobernado para un catálogo OpenMetadata-shaped. El
contrato está separado del servidor: BAGO construye `ExecutionRequest`, emite
un `Permit` acotado y sólo entonces llama al cliente de transporte.

El adapter cubre:

- `search`: búsqueda de entidades y normalización de ownership, tags, versión y autoridad.
- `get_lineage` / `add_lineage`: lectura y escritura de edges direccionales.
- `assign_ownership`: asignación de usuario/equipo como owner.
- `register_schema_version`: actualización de versión y schema extension.
- `create_quality_rule`: definición de test de calidad TABLE/COLUMN.

La implementación acepta un cliente inyectado para tests y evidencia. Cuando
no se inyecta cliente, dispone de un transporte JSON mínimo basado en la
biblioteca estándar; no se invoca durante la evidencia offline.

## Boundary de gobernanza

| Operación | Efecto BAGO | Permitido automáticamente |
|---|---|---:|
| `search` | `READ` | Sí, si está en allowlist |
| `get_lineage` | `READ` | Sí, si está en allowlist |
| `add_lineage` | `WRITE` | Según policy |
| `assign_ownership` | `WRITE` | Según policy |
| `register_schema_version` | `WRITE` | Según policy |
| `create_quality_rule` | `CREATE` | Según policy |

Cada llamada produce `MetadataCatalogReceipt`, incluso cuando es denegada,
expira el permiso, alcanza el rate limit o falla el transporte. Los retries
sólo aplican a timeout, throttle y red; un `401/403` no se reintenta.

## Mapeo API

El adapter normaliza el contrato hacia endpoints OpenMetadata conocidos:

- `GET /api/v1/search/query` para discovery.
- `GET /api/v1/{entityType}/{id}/lineage` y `PUT /api/v1/lineage` para lineage.
- `PATCH /api/v1/{entityType}/{id}` para ownership/version extension.
- `POST /api/v1/dataQuality/testDefinitions` para quality rules.

El payload de lineage usa `fromEntity`, `toEntity` y `lineageDetails`, y la
calidad se expresa como test definition con `TABLE` o `COLUMN`.

## Evidencia reproducible

```powershell
python -m pytest tests/test_openmetadata_adapter.py -v
python scripts/generate_l8_catalog_evidence.py
```

La evidencia está en
`evidence/l8_openmetadata_catalog.md`. Usa un cliente en memoria y demuestra:

`search (2 entidades)` → `source → asset → chunk (2 edges)` → `ownership` →
`schema version 2.0` → `quality rule` → `receipts`.

Esto verifica el contrato y la gobernanza del adapter; no es una medición de
OpenMetadata real.

## Validación live pendiente

La ejecución real requiere un servidor OpenMetadata local o remoto, su API y
credenciales. La documentación oficial del quickstart Docker pide Docker y
Compose, y recomienda al menos 6 GiB de memoria y 4 vCPUs para el despliegue
local ([quickstart Docker](https://docs.open-metadata.org/v1.12.x/quick-start/local-docker-deployment)).

En este checkout, `docker --version` y `docker compose version` devuelven
`command not found`; por eso Docker/OpenMetadata live queda `NOT_RUN`, no
`VERIFIED`. Cuando el runtime exista, la validación debe comprobar el servidor,
la búsqueda, el lineage y la autorización del usuario/equipo antes de elevar
la afirmación.

OpenMetadata documenta que la búsqueda se expone en `/api/v1/search/query`,
que el lineage se crea con `PUT /v1/lineage` y que las definiciones de calidad
son recursos API propios ([APIs](https://docs.open-metadata.org/v1.12.x/api-reference/main-concepts/metadata-standard/apis),
[lineage](https://docs.open-metadata.org/v1.12.x/api-reference/lineage/add),
[test definitions](https://docs.open-metadata.org/v1.11.x/api-reference/data-quality/test-definitions)).
