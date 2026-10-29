# Independent review — Consultar archivo submit

Candidata: `bf4ce08b730e4616f3a5caf9e3111b8d8ec1a3e6`, base `bf4ce08b730e4616f3a5caf9e3111b8d8ec1a3e6`.

**Resultado: 0 P0 y 0 P1 funcionales nuevos observados por lectura del diff.** El cambio acotado de fuente es coherente con la causa reproducida por el implementador.

## Motivo

El portal saca el dialog y sus formularios del form del composer en el DOM. El onSubmit del dialog corta además la propagación de eventos de React a sus ancestros lógicos. El handler de KnowledgeIngest mantiene preventDefault y la petición prevista. El cambio no altera el modelo seleccionado, el payload ni la ruta backend.

La ubicación normal bajo `.control-chat` conserva los estilos de ámbito. El fallback a `document.body` sirve en un render standalone con DOM. El cambio de contenedor inicial body→control-chat coincide con el render de apertura y la effect dependiente de activeTool abre el nuevo ref. El cierre, cancelación y foco del launcher siguen en los handlers existentes; son razonamientos estáticos, no pruebas nativas de navegador.

## Hallazgos P2

- **REV-P2-01 — FORMATTING**: Source-only git diff --check reported trailing whitespace on added CRLF lines during review. Normalize intended source line endings and rerun this static check before publication; no source behavior change required.

- **REV-P2-02 — TEST_SCOPE**: New tests exercise nested-form exclusion and one intended POST with no composer submit/draft loss. They do not exercise native dialog close/cancel focus restoration or standalone body fallback. showModal/close are simplified stubs and close does not dispatch close. Keep these lifecycle/fallback cases explicit as not verified by these two tests. Existing real-browser evidence can cover them if it includes those actions; do not infer native focus behavior from jsdom stubs.

- **REV-P2-03 — PUBLICATION_SCOPE**: Build regenerated tracked derived outputs with broad changes beyond the seven-line source diff. dist/index.html now names new hashed assets while git tracks no assets in that directory. This is an artifact/publication-scope observation, not a newly demonstrated source regression. Choose deliberately whether derived artifacts belong in the PR; avoid publishing a changed bare dist index as a standalone frontend without its built assets.

## Calidad de las pruebas nuevas

Las dos pruebas cubren la ausencia de form ancestro, la permanencia bajo control-chat, un solo POST al endpoint de conocimiento, ausencia de submit del composer y conservación del borrador. Son condiciones observables relevantes al fallo. Las sustituciones de showModal/close no cubren por sí mismas cancel, close nativo o devolución del foco. No hay caso standalone sin control-chat ni prueba de Enter explícita en estas dos pruebas.

## Verificación y límites

Solo se ejecutó la comprobación estática git diff --check. Suites, build, navegador y modelos no se volvieron a ejecutar por instrucción del padre. Las afirmaciones de 15 pruebas focalizadas PASS, build PASS y consulta real por navegador son evidencia suministrada por el implementador; este informe no las convierte en una reejecución independiente.

No se han editado archivos del checkout. La identidad de los archivos revisados está en review.json. La higiene de publicación y la normalización del diff deben quedar cerradas antes del commit final.
