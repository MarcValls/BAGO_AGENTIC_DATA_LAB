# Tutorial demo: Kebap Ruta 7

Video en español: [`tutorial-kebap.mp4`](tutorial-kebap.mp4). Subtítulos: [`tutorial-kebap.srt`](tutorial-kebap.srt).

> Empresa, sucursales, registros, reglas y QA ficticios. Se usaron dos perfiles guardados en la aplicación y dos turnos de agente mediante Ollama Cloud (`gemma4:31b`). No hay datos de clientes reales ni se ejecutaron pagos o reembolsos.

## Recorrido

1. En Agent Builder crea el extractor y el revisor descritos en [`cloud-runs/profiles.json`](cloud-runs/profiles.json). El perfil hereda el modelo del proveedor configurado.
2. En Chat elige el extractor y autoriza solo `inputs/orders.csv` para ese mensaje. Pide el JSON con campos explícitos y nulos para lo desconocido.
3. Elige el revisor; autoriza el CSV, `inputs/policy.md` y `inputs/qa-expected.md`. Pide decisiones por registro, cita de rutas/líneas y confirma que no se ejecutaron acciones.
4. Compara la salida y los cuatro casos con los recibos, trazas locales y QA.

## Fixtures y resultados

Entradas: [`inputs/orders.csv`](inputs/orders.csv), [`inputs/policy.md`](inputs/policy.md), [`inputs/qa-expected.md`](inputs/qa-expected.md). La extracción JSON está en [`extracted/orders.json`](extracted/orders.json); el análisis, en [`extracted/decisions.json`](extracted/decisions.json). Las respuestas originales y perfiles se conservan en `cloud-runs/`; evidencia y hashes, en [`extracted/run-evidence.json`](extracted/run-evidence.json).

| ID | Resultado | Valor calculado |
|---|---|---|
| K-901 | 42 min · delivery | Elegible · 2,50 € |
| K-902 | 30 min exactos | No elegible |
| K-903 | Pickup | No elegible |
| K-904 | Sin finalización | Pendiente |

Todos los eventos de lectura registrados fueron ALLOW. Las trazas de esta ejecución son `local_only`, no exportadas a Jaeger/cloud. El extractor omitió `evidence_paths` en su JSON, aunque los recibos locales enlazan archivos y hashes; se explica en el video.

## Alcance

Tipo de perfil `RAG` no significa que se haya creado un índice vectorial del negocio: este tutorial lee ficheros autorizados por mensaje. Los resultados solo validan los fixtures, no una política comercial real. Antes de producción deben verificarse las reglas con el negocio y revisarse manualmente antes de actuar.
