# W04 — CSV gobernado desde el chat principal

## IMPLEMENTADO

El recorrido es **chat principal → Recursos → Consultar archivo → CSV del
proyecto**. La alternativa Texto / Markdown mantiene la ingestión ya existente.
La selección CSV usa exclusivamente los metadatos de las API de permisos y
directorios; todavía no lee el contenido, no importa el archivo y no crea un
corpus. La vista Tabla / Texto no participa en este recorrido.

La persona selecciona un CSV relativo al proyecto, escribe su pregunta, revisa
el separador de columnas y el separador decimal y autoriza esa petición. El
frontend exige el READ guardado existente y solicita una autorización exacta a
`/api/workspace-read/authorizations`. Comprueba el archivo único, la identidad del
proyecto, el binding, la revisión de política y el SHA-256 de la pregunta y las
opciones canónicas antes de llamar a `/api/chat/control`.

La autorización pertenece a la conversación y revisión concretas. Un cambio de
proyecto, propietario, conversación o revisión descarta la selección y el
consentimiento; una respuesta tardía no se incorpora al contexto nuevo. Cada
pregunta solicita una autorización nueva. Este envío no hereda autorizaciones
web/documentales ni consume el borrador todavía no enviado del compositor.

Cancelar, cerrar el diálogo o cambiar de contexto solicita revocación mediante el endpoint
existente. La UI solo confirma la revocación si recibe `revoked: true`; una
respuesta negativa o un error conservan un diagnóstico de revocación no
confirmada, incluso después de cerrar el formulario. Cuando la petición ya ha
llegado al chat, cancelar mantiene el reintento pendiente hasta el cierre HTTP
real y después sincroniza únicamente la revisión y fecha de la conversación
exacta, sin aplicar el contenido tardío. Un error de transporte o identidad
bloquea el reintento y pide reabrir la conversación desde el historial. El backend
sigue siendo la autoridad sobre STOP, caducidad, política, identidad, consumo y
acceso físico.

La respuesta vuelve al chat normal, con la operación y convención decimal
visibles, y conserva `sources`, `read_events` y `csv_analysis` al volver a abrir
la conversación. La evidencia CSV muestra también el hash del archivo original.

Se corrigió además un bloqueo observado del menú Recursos en móvil: el scroll
horizontal de la fila de acciones recortaba su menú hacia arriba. Dos líneas de
CSS permiten el desbordamiento únicamente mientras el menú está abierto.

## VERIFICADO — interfaz y regresión automatizadas

El check registrado `ui` final ejecutó **79 pruebas PASS en 7 archivos**, el build
TypeScript/Vite, la sintaxis del runner de navegador y `git diff --check`.

- **30 pruebas CSV**: metadatos sin lectura, consentimiento por pregunta/opciones,
  READ guardado necesario, ruta relativa, rechazo de rutas externas y no CSV,
  grant único y exacto, hashes y proyecto/política coincidentes, denegación del
  servidor, revocación al cancelar/cerrar, revocación no confirmada, descarte de
  respuestas tardías y cambios de contexto, conversación nueva y borrador
  preservado, cancelación y reintento con revisión sincronizada, fallo de
  transporte al cancelar, propietario ajeno y diagnóstico tras cerrar el modal.
- **49 pruebas de regresión**: envío de recursos fuera del formulario del
  compositor, preview/parser Tabla CSV, web pública, selección de proveedor y
  contexto del panel de chat.

Las pruebas Vitest controlan el transporte HTTP. Acreditan el despacho y las
defensas de la UI; no acreditan por sí mismas lectura física, STOP del servidor
ni interpretación de un proveedor real. Las pruebas Tabla CSV acreditan la
preservación del visor, no sustituyen las del chat.

Evidencia final: `ui-check-04.receipt.json`,
`ui-check-04.runtime-receipt.json`, `ui-check-04.runtime-stdout.log`,
`ui-check-04.runtime-stderr.log` y `ui-check-04.result.json`.
Execution ID del controlador: `5956795675394e7e945d59823ec2bb45`.
El build conserva el aviso previo de bundle superior a 500 kB; termina con
código 0. Los generados versionados `.build` y `dist` se restauraron para
entregar los cambios fuente.

La revisión independiente posterior cerró dos defectos P2: reintento después de
cancelar con revisión obsoleta y revocación fallida oculta al cerrar el modal.
El revisor `csv_engine` ejecutó los ocho casos focales de regresión con resultado
8 PASS / 22 SKIP. El check completo posterior de 79 pruebas incluye esos casos.

## F11 en navegador con lectura real

El runner `frontend/tests/csv-chat/browser-f11.cjs` no intercepta HTTP, no simula
grants y no sustituye la respuesta del chat. La API, el archivo, la política
READ, las autorizaciones, el parser, el cálculo, las trazas y la persistencia
son reales dentro de un proyecto efímero de pruebas. El proveedor de
**interpretación es CONTROLLED** (`query-plan-fixture`, mostrado en la UI como
«Interpretación controlada · no modelo real»). Esto no demuestra el rendimiento
de un modelo real ante cualquier pregunta.

Se reinició el backend antes de `final-browser`. Los
JSON registran los hashes de los archivos relevantes en cada invocación; se
compararon de nuevo al terminar y seguían siendo idénticos. El archivo original
también conservaba su hash al acabar. Ese ensayo precede a las dos correcciones
de cancelación; no debe atribuirse su manifest a la fuente posterior.

El ensayo `post-review-browser` usó la fuente posterior: escritorio PASS, móvil
con lectura/cálculo HTTP 200 pero FAIL al reabrir el historial. El GET posterior
exacto devolvió la misma conversación con revisión 0 y mensajes vacíos, frente
a la revisión 2 devuelta por el POST. La discrepancia está preservada en
`post-review-browser/mobile.json` y `mobile-persistence-diagnostic.json`. No se
ha clasificado como fallo del locator ni se ha convertido ese intento en PASS.

La investigación independiente reprodujo sustituciones físicas del SQLite en el
workspace compartido: cambio de inode y retroceso de tamaño/mtime, incluso con
una variante que cierra las conexiones. El actor que sustituye el archivo no
está identificado. El contraste comunicado por W12 fue 6/6 ensayos PASS en
`/tmp` (3.000 appends), frente a 2/6 con sustitución de inode en el workspace.
La evidencia detallada corresponde al informe independiente
`../review/SQLITE_RUNTIME_INCIDENT.md`. No se modificó el store de la aplicación
para ocultar esta incidencia.

La pasada causal final **`causal-browser`** aisló únicamente el almacenamiento
del fixture en `/tmp/adl-csv-browser-fixture-20261101`. Conservó las fuentes del
producto, el contenido original y el proveedor de interpretación controlada.
El runner guarda ahora el GET exacto de reapertura, compara revisión e ids de
mensajes y verifica la igualdad de `csv_analysis`, `sources` y `read_events`.
Además registra `/api/runtime/storage`, el SHA-256 de `server.py` al importar y
el inode, mtime y hash SQLite antes/después. La persistencia y la visibilidad se
registran por separado.

Los resultados finales siguientes corresponden a `causal-browser`:

| Comprobación | Escritorio | Móvil |
| --- | --- | --- |
| Navegador | Chromium 141.0.7390.37, Linux | Chromium 141.0.7390.37, Linux |
| Viewport | 1440 × 1000 | 390 × 844 |
| Hora UTC inicial | 2026-11-01 04:56:13 | 2026-11-01 04:56:17 |
| Resultado HTTP y CSV | 200, `answered` | 200, `answered` |
| Consola / errores de página | 0 / 0 | 0 / 0 |
| Selector: scrollWidth / clientWidth | 1422 / 1422 | 372 / 372 |
| Recarga y reapertura de la conversación exacta | PASS | PASS |
| GET exacto: revisión / mensajes | 2 / 2 | 2 / 2 |
| SQLite inode antes / después | 1607749 / 1607749 | 1607749 / 1607749 |
| Evidencia | `causal-browser/desktop.json` y PNG | `causal-browser/mobile.json` y PNG |

Conversaciones reales del ensayo final:

- Escritorio: `conv_cd4452728ba7405d84632f98ea27de18`.
- Móvil: `conv_395a0d6ad5ee42ab98408eec00bcdcf3`.

Check administrado `browser`: **PASS**, execution ID
`a95adc5a5fa74d459498ef672215d4e6`; recibos y logs en `causal-browser`.
El `server_source_sha256_at_import` fue
`a7949d8df192c142232ff05602d1b46a184443c02a504656c13fd4a6de33c629`, coincidente
con el árbol fuente registrado. El proceso se mantuvo en 38526 durante ambos
ensayos. Los hashes de las fuentes se volvieron a contrastar al terminar.

Archivo seleccionado: `demo-usuario/archivo/pedidos-final.csv`, de 183 bytes,
SHA-256 `8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5`.
Pregunta enviada: «Analiza pedidos: importe descontado por pedido, pendientes
por estado y total general.»

La respuesta contiene la fórmula
`importe = unidades × precio_unitario × (1 − descuento_pct ÷ 100)`, la
agrupación por estado y la convención decimal punto, junto al resultado:

| Filas CSV | Pedido / estado | Importe calculado |
| --- | --- | ---: |
| 2 | P001 | 199.800 |
| 3 | P002 | 54.00 |
| 4 | P003 | 47.5000 |
| 2, 4 | pendiente | 247.3000 |
| 3 | entregado | 54.00 |
| 2, 3, 4 | total general | 301.3000 |

La cobertura es 3 de 3 filas, con entrada completa. Los ceros conservan la
representación Decimal; los valores numéricos son 199.80, 54.00, 47.50, 247.30 y
301.30. Los JSON incluyen la interpretación, las filas fuente, los hashes y la
conversación persistida. Los identificadores de autorización están redactados.

La comprobación posterior a la recarga selecciona explícitamente la conversación
por su id y verifica el id de su mensaje guardado. El chat principal arranca en
blanco por diseño (`historySelection=explicit`); no se presupone reapertura
automática de historial.

## Historial de intentos preservado

| Intento | Resultado observado | Clasificación y resolución |
| --- | --- | --- |
| `attempt-01-desktop` | F11 manual PASS, capturas de selección y resultado | Primer backend de ensayo, anterior a los últimos cambios. No es la evidencia final. |
| `attempt-02-mobile` | FAIL antes de autorizar | Defecto de producto: el menú Recursos quedaba recortado por overflow. Corregido y repetido. |
| `attempt-03-mobile` | Lectura HTTP 200 y cálculo correctos; runner FAIL tras reload | Error del runner: esperaba historia automática. Corregido para reabrir la conversación exacta. |
| `attempt-04-browser` | PASS escritorio y móvil, incluida persistencia | Backend de ensayo anterior al reinicio final; preservado sin sobrescribir. |
| `final-browser` | PASS escritorio y móvil | Backend reiniciado; anterior a las correcciones P2 de cancelación. |
| `post-review-browser` | Escritorio PASS; móvil HTTP200 answered y FAIL en reapertura | GET real posterior devuelve revisión0/mensajes vacíos. Incidente del entorno compartido preservado; actor desconocido. |
| `causal-browser` | PASS escritorio y móvil | Datos del fixture aislados en `/tmp`, GET exacto y visibilidad PASS, inode estable y fuente del servidor contrastada. |
| `ui-verification-attempt-01.*` | Tests y build PASS, recibo FAIL | Error de evidencia: `--output` declaraba un archivo que el proceso no había creado. Recibo original preservado. |
| `ui-verification.*` / `ui-check-02.*` | FAIL por `spawnSync npm EPERM` | Restricción del sandbox al capturar pipes; ninguna expectativa se relajó. |
| `ui-check-03.*` | PASS | `stdio` heredado y resumen generado por el proceso; resultados y logs ligados al recibo. |
| `ui-check-04.*` | PASS | 79 pruebas y build tras cerrar ambos P2 de cancelación; fuente revisada. |

Los documentos y pruebas históricos `user-demand-20261101` no se han modificado.

## Reproducción del navegador

Requisitos: frontend y API reales ejecutándose, un proyecto de pruebas con el CSV
original y READ guardado, y el proveedor de interpretación controlada descrito
por el fixture de integración de esta misión. La variante final del fixture
expone en `/api/runtime/storage` el id del proceso y hash del servidor al importar;
el runner los exige para vincular la evidencia. Playwright 1.56.1 / Chromium
141 se instalaron fuera de las dependencias del repositorio.

Desde la raíz del repositorio:

```bash
ADL_URL=http://127.0.0.1:5173 \
ADL_PLAYWRIGHT_MODULE=/absolute/path/to/node_modules/playwright \
PLAYWRIGHT_BROWSERS_PATH=/absolute/path/to/playwright-browsers \
ADL_EXPECTED_DATA_ROOT=/absolute/path/to/isolated-fixture/data \
ADL_EVIDENCE_DIR=/absolute/path/to/new-evidence-directory \
node frontend/tests/csv-chat/browser-f11.cjs desktop mobile
```

El directorio de evidencia debe ser nuevo: el runner rechaza sobrescribir un
resultado anterior. `ADL_CSV_PATH` permite cambiar la ubicación relativa del
CSV, conservando el mismo contenido esperado. Se requiere un entorno capaz de
ejecutar Chromium; este sandbox necesitó ejecución escalada para el navegador.
Los hashes del árbol fuente por sí solos no prueban qué código cargó un proceso
ya iniciado: debe reiniciarse el servidor al ligar una ejecución a nuevas
fuentes, como se hizo en el ensayo final.

## NOT_RUN / alcance pendiente de otras verificaciones

- Navegador y servidor Windows: **NOT_RUN**.
- Proveedor de IA real y variaciones semánticas de preguntas libres:
  **NOT_RUN** en W04; la interpretación del ensayo está controlada.
- El actor que sustituyó SQLite en el workspace compartido sigue sin
  identificarse. El ensayo final acredita la lectura y persistencia en el
  almacenamiento aislado indicado, sin garantizar la durabilidad del entorno
  compartido afectado por ese incidente.
- Cancelación, caducidad, revocación y carreras del backend: W04 verifica su
  despacho/diagnóstico en UI; sus garantías físicas corresponden a las pruebas
  backend e independientes W02/W12.
- F10 y F12 completos por HTTP y su contraste con F11 corresponden al informe
  independiente W12. Este informe acredita F11 y no atribuye al visor Tabla una
  lectura desde chat.
