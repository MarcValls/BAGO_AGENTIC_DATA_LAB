# L8 · OpenMetadata Metadata Catalog

## Alcance

L8 añade un adapter gobernado para un catálogo OpenMetadata-shaped. El
contrato está separado del servidor: BAGO construye `ExecutionRequest`, emite
un `Permit` acotado y sólo entonces llama al cliente de transporte.

El adapter cubre:

- `search`: búsqueda de entidades y normalización de ownership, tags, versión y autoridad.
- `get_lineage` / `add_lineage`: lectura y escritura de edges direccionales.
- `assign_ownership`: asignación de usuario/equipo como owner.
- `register_schema_version`: actualización versionada de `schemaDefinition`.
- `create_quality_rule`: definición de test de calidad TABLE/COLUMN.

La implementación acepta un cliente inyectado para tests y evidencia. Cuando
no se inyecta cliente, dispone de un transporte JSON mínimo basado en la
biblioteca estándar. El transporte acepta un Bearer JWT opcional mediante
`OpenMetadataCatalogPolicy(auth_token=...)`; el token sólo vive en memoria,
no aparece en receipts ni se escribe en evidencia.

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
- `GET /api/v1/lineage/{entityType}/{id}` y `PUT /api/v1/lineage` para lineage.
- `PATCH /api/v1/tables/{id}` con `application/json-patch+json` para ownership y
  `schemaDefinition` versionada.
- `POST /api/v1/dataQuality/testDefinitions` para quality rules.

El payload de lineage usa `fromEntity`, `toEntity` y `lineageDetails`, y la
calidad se expresa como test definition con `TABLE` o `COLUMN`.

## Evidencia reproducible

```powershell
python -m pytest tests/test_openmetadata_adapter.py -v
python scripts/generate_l8_catalog_evidence.py
python scripts/run_l8_openmetadata_live_validation.py
```

La evidencia está en
`evidence/l8_openmetadata_catalog.md`. Usa un cliente en memoria y demuestra:

`search (2 entidades)` → `source → asset → chunk (2 edges)` → `ownership` →
`schema version 2.0` → `quality rule` → `receipts`.

Esto verifica el contrato y la gobernanza del adapter; no es una medición de
OpenMetadata real.

## Validación live local

El checkout incluye el compose oficial fijado a OpenMetadata `1.12.6` en
`infra/openmetadata/docker-compose.yml`. La validación local se ejecuta con:

```powershell
docker compose -p bago-openmetadata -f infra/openmetadata/docker-compose.yml up -d
python scripts/run_l8_openmetadata_live_validation.py
docker compose -p bago-openmetadata -f infra/openmetadata/docker-compose.yml ps --all
```

La documentación oficial del quickstart Docker pide Docker y Compose, y
recomienda al menos 6 GiB de memoria y 4 vCPUs para el despliegue local
([quickstart Docker](https://docs.open-metadata.org/v1.12.x/quick-start/local-docker-deployment)).
El despliegue ejecutado en este checkout responde `HTTP 200` en
`http://localhost:8586/healthcheck`; las migraciones terminaron con código 0.

`evidence/l8_openmetadata_live.md` registra la ejecución real y sus receipts:

`health` → `JWT login` → `search` → `add_lineage` → `get_lineage` →
`assign_ownership` → `register_schema_version` → `create_quality_rule` →
denegación `REQUIRE_HUMAN` antes del transporte.

El script crea recursos temporales con nombres únicos y elimina sólo sus IDs al
final. Por tanto, `L8 VERIFIED (local live)` significa servidor Docker local,
transporte HTTP autenticado y operaciones del adapter verificadas; no significa
OpenMetadata remoto, AWS, aislamiento de sistema operativo ni producción.

OpenMetadata documenta que la búsqueda se expone en `/api/v1/search/query`,
que el lineage se consulta bajo `/api/v1/lineage`, se crea con `PUT /v1/lineage`
y que las definiciones de calidad son recursos API propios
([APIs](https://docs.open-metadata.org/v1.12.x/api-reference/main-concepts/metadata-standard/apis),
[lineage](https://docs.open-metadata.org/v1.12.x/api-reference/lineage/add),
[test definitions](https://docs.open-metadata.org/v1.11.x/api-reference/data-quality/test-definitions)).
