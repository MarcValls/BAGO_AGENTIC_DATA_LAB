# Revisión independiente de trazabilidad — Continuidad gobernada / Brave R5

**Resultado:** `NO_GO` para validar cierre. Revisión de solo lectura, candidate-bound. El rol formal del work item de revisión en la misión es `verification-engineer`; la skill `trace-observability-engineer` pidió atención a identidad, correlación, cronología/causalidad, retención y fallos. El resultado no está registrado como handoff validado: `teamctl inspect INDEPENDENT_REVIEW` falla por la dependencia `LOCAL_POLICY`.

## Identidad revisada

- Mission: `CODEX_GOVERNED_CONTINUITY_20261031`.
- Candidate: `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`.
- Scope: `0af844db09c04531999970ed71e0bce9ed1f51245b48416d0453a7bc7cef9df9`.
- Brave handoff file SHA-256: `f547de10b5fee7482d2e987278af497520763cb053bb839a01c9fe9b3e832c02`.
- Runtime / cleanup execution IDs: `82c2292c60ea403e9dadb313be96202d` / `8d3041fd47fa4d4bb821aca94f642596`.
- The candidate and scope match across handoff and both receipts. All 29 declared Brave handoff output paths exist and match their hashes. The handoff file SHA matches the runtime state entry.

## Hallazgos

### P1 — AC-01 no está probado al nivel declarado

El registro local que alimentó el snapshot clasificó AC-01 como `MET` por continuidad observada dentro de un turno y dice que eso no demuestra lanzamiento automático de agentes ni continuidad cross-session. La evidencia soporta `PARTIAL`, no el criterio completo. GitHub está corregido a `PARTIAL`; T1 permanece abierto parcialmente.

### P1 — Fuentes de evidencia no recuperables desde GitHub

La rama contiene el resumen JSON y una captura del contenido de fixture; no contiene el handoff ni los recibos fuente. Por ello, un lector de GitHub no puede recalcular los hashes de runtime/cleanup ni validar independientemente el intercambio. La captura no muestra el canal nativo ni prueba el handshake. El snapshot es una síntesis, no un paquete de evidencia pública reproducible.

### P1 — Integridad bloquea la revisión formal

`teamctl inspect INDEPENDENT_REVIEW`, `inspect LOCAL_POLICY`, `verify` y `pair` fallan con `output sha256 mismatch` para `.bago/goals/operational-continuity-governance-20261031/status.json`. El estado administrativo de `INDEPENDENT_REVIEW=READY` no valida dependencias. No se reclamó ni se registró un handoff formal. No se debe restaurar o re-firmar en silencio el recibo congelado.

### P2 — Correlación proceso→evento incompleta

El runtime snapshot contiene dos PID con los mismos argumentos mientras el puerto estaba abierto; cleanup confirma que ambos terminaron. No hay una identidad de proceso por mensaje `connectNative`, así que no se puede explicar cuál proceso atendió cada solicitud ni la duplicación. No se observó un recibo duplicado.

### P2 — `inspect PASS` no equivale a integridad

`teamctl inspect BRAVE_E2E_R5` y `inspect P2_HOST_R5` informan `PASS` con `evidence_classification=INTEGRITY_NOT_REQUESTED`. La validación manual de los 29 outputs de Brave sí pasó, pero el `verify` global sigue fallando por LOCAL_POLICY.

## Trazas y recibos

Los cinco IDs de protocolo son únicos: `r5-hello-01`, `r5-valid-preview-01`, `r5-deny-digest-01`, `r5-deny-origin-01`, `r5-deny-shell-01`. La secuencia es `ready → preview_receipt → denied ×3`; denegaciones tienen `accepted=false`. Preview y denegaciones de digest/origen comparten `tab_id` y `document_epoch`; shell no tiene esos campos. Todas indican `content_retained=false`.

La correlación work item→check→execution→receipt está explícita por IDs estables. El array no trae timestamp individual para cada mensaje, solo `recorded_at_utc` para el conjunto. La correlación de los dos PID con cada mensaje está ausente. La denegación shell no se transforma en éxito. El intento 6 y anteriores continúan como `FAIL`; intento 7 y cleanup como `PASS`.

## Matriz T1–T12

| Criterio | Estado revisado | Motivo |
|---|---|---|
| T1 | `PARTIAL` | Solo continuidad intra-turno observada. |
| T2–T7 | `OPEN` | No hay evidencia suficiente de los casos negativos respectivos. |
| T8 | `MET` | Se verificaron los SHA de los archivos archivados previos. |
| T9 | `MET` | 13 escenarios registrados `PASS`; ejecución fallida permanece `FAIL`. |
| T10–T12 | `OPEN` | Sin evidencia suficiente. |

## Cognitive Spiral y corrección posterior

`NOT_RUN`: no se ejecutaron ciclos cognitivos. La conclusión inicial sobre runtime ausente fue una búsqueda incompleta. El controlador real está en la raíz de la skill instalada y su identidad 1.4.7 pasó. El [relevo real R2](RELAY.md) se ejecutó y cerró; ese cierre solo valida consistencia del snapshot y no elimina los P1 de esta revisión.

**P0:** ninguno observado dentro del material revisado; esto no equivale a una certificación de ausencia sistémica. **P1 abiertos:** tres, descritos arriba. **P2 abiertos:** dos. **Handoff validado:** no.
## Actualización posterior: cognición LIVE

La auditoría cognitiva de la misión real ya se ejecutó con tres procesos, seis decisiones LIVE y verificación independiente. La integración pasó; los mismos bloqueos originales fueron observados como FAIL. Esta evidencia no valida el handoff original de teamctl. [COGNITIVE.md](COGNITIVE.md).
