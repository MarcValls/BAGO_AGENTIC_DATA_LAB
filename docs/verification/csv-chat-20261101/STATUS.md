# Lectura gobernada de CSV desde el chat principal

Fecha: 1 de noviembre de 2026. Rama: `codex/governed-csv-chat-20261101`.

## Estado y alcance

**IMPLEMENTADO:** selección de un CSV del proyecto, autorización para una pregunta
concreta, lectura acotada, consultas y cálculos deterministas, respuesta con
procedencia y persistencia en el chat principal.

**VERIFICADO:** F10–F12 mediante HTTP con archivos, política READ, grants, toolkit
y SQLite reales; 57 casos HTTP independientes; navegador Chromium Linux de
escritorio y móvil con estado aislado. La interpretación del proveedor está
controlada y se identifica expresamente como tal.

**NOT_RUN:** interpretación con un modelo real, Windows/Brave del usuario,
instalación y proyectos reales del usuario, despliegue y STOP global en otros
recorridos de ADL. Validar la estructura del plan no demuestra que todo plan
válido represente correctamente la intención del usuario.

La PR [#112](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/112) ya estaba
fusionada al inspeccionarla: `2026-11-01T04:08:36Z`, merge
`16b74a590889d6b42d7889abc8cd114b35c5dbf1`. Esta implementación parte de ese
`origin/main` actualizado. Se conserva la consulta de metadatos en
[PR112_METADATA.json](closure/PR112_METADATA.json) y la inspección inicial en
[BASELINE.json](plan/BASELINE.json).

## Recorrido disponible

1. Seleccionar un proyecto registrado y guardar READ para la carpeta necesaria
   mediante los permisos existentes, si aún no lo tiene.
2. En **BAGO5 → Chat → Recursos → Consultar archivo → CSV del proyecto**, elegir
   el archivo o introducir su ruta relativa. La selección consulta metadatos;
   todavía no lee las celdas.
3. Formular la pregunta y revisar delimitador y convención decimal. Por ejemplo:
   «Analiza pedidos: importe descontado por pedido, pendientes por estado y total
   general».
4. Marcar **Autorizo la lectura de este CSV para esta pregunta y estas opciones**
   y pulsar **Autorizar y consultar en el chat**.
5. Revisar la fórmula, filtros, filas originales, cobertura y hashes de la
   respuesta. Cada pregunta nueva requiere una autorización nueva.

Cancelar solicita revocación inmediatamente. La interfaz espera el cierre real
de la petición y sincroniza únicamente su revisión, sin mostrar contenido tardío.
Si no puede confirmar revocación o estado, conserva el diagnóstico y bloquea el
reintento hasta reabrir la conversación. La revocación no deshace una lectura ya
realizada ni puede retirar una petición ya enviada al proveedor; sí impide
efectos posteriores y la publicación pendiente bajo el grant revocado.

## Componentes reutilizados y límites

| Componente existente | Integración |
| --- | --- |
| `WorkspaceReadAuthorizations` | Grant opcional CSV, único, de 300 segundos, ligado a propietario, conversación/revisión, proyecto/root/binding/política, archivo, pregunta y opciones. Revocación en el mismo registro; sin segundo almacén de permisos. |
| `ProjectPermissions` y `workspace_read` | READ guardado y grant exacto son necesarios. Se reutilizan la lease de política, el sandbox y el lector. Un READ amplio no amplía la selección CSV. |
| Document toolkit | Parser compartido de bytes y motor `csv_query` de planes finitos. Sin ingesta, índice, corpus nuevo, `eval`, comandos o lectura de otros archivos. |
| Chat principal y conversaciones | `/api/chat/control` calcula desde la instantánea realmente leída y conserva `csv_analysis`, fuentes, recibos y traza. No hay un segundo LLM que reescriba las cifras. |
| teamctl STOP | Se consulta el controlador fijo de la aplicación y el estado de misión del proyecto. Las fronteras de IO/publicación mantienen política → STOP → grant y revalidan después de esperar. Nunca mantienen esos locks durante inferencia. |

Se mantienen **256 KiB y 250 líneas físicas**. El CSV debe ser UTF-8, con o sin
BOM. Se admiten coma, punto y coma, tabulador o barra vertical, con autodetección
o selección explícita; el decimal es punto o coma, sin separadores de miles
implícitos. Se rechazan archivos truncados, CSV malformados y valores numéricos
ambiguos. Selección, filtros, columnas derivadas, agrupación, cuenta, suma,
mínimo, máximo y media tienen límites de complejidad y salida.

Los cálculos usan Decimal con precisión 38 y revelan redondeo cuando existe.
El límite visual de filas no recorta el conjunto utilizado para agregar. Cada
respuesta incluye SHA-256 del archivo, del plan y del resultado, además de las
filas y ubicaciones de origen.

Un estado teamctl heredado o no verificable **bloquea** esta ruta con
`STOP_STATE_UNVERIFIABLE`. El runtime histórico del repositorio, versión 0.1.0,
no se migra ni se borra. Las fixtures nuevas que pasan no acreditan que un
proyecto legacy pueda consultarse sin resolver su estado mediante el mecanismo
existente. `local_rag.py` mantiene su restricción de texto/Markdown.

## F10–F12: evidencia nueva, historia intacta

Los estados originales de `docs/verification/user-demand-20261101/` permanecen
intactos. Los resultados siguientes son ejecuciones nuevas y no sustituyen el
recorrido histórico de 38 minutos.

| Flujo | Histórico | Nueva reproducción verificada |
| --- | --- | --- |
| F10 | BLOCKED: una ruta escrita no bastaba | La ruta sin permiso sigue sin dar acceso. Tras READ y autorización exacta, una lectura real y análisis persistido; revisión 4 contando el intercambio inicialmente denegado. |
| F11 | BLOCKED: Consultar archivo usaba fuentes de texto/Markdown | La opción CSV usa metadatos → grant existente → chat, sin RAG. HTTP y navegador de escritorio/móvil verifican datos y persistencia. |
| F12 | FAIL: READ guardado no terminaba en análisis | READ por sí solo sigue sin conceder la petición. Con grant exacto, lectura, cálculo, fuentes y dos mensajes persistidos. |

CSV histórico: `demo-usuario/archivo/pedidos-final.csv`, **183 bytes**,
SHA-256 `8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5`.

| Pedido | Cálculo aplicado | Importe |
| --- | --- | ---: |
| P001 · Alba | 12 × 18,50 × (1 − 10/100) | 199,80 |
| P002 · Bruno | 6 × 9,00 × (1 − 0/100) | 54,00 |
| P003 · Carmen | 8 × 6,25 × (1 − 5/100) | 47,50 |

**Pendientes: 247,30. Total general: 301,30.** El archivo permanece intacto.
Los resultados conservan los decimales originales, incluidos ceros adicionales.

Véanse [F10](review/http/F10.json), [F11](review/http/F11.json),
[F12](review/http/F12.json), [revisión independiente](review/REVIEW.md) y
[navegador e interfaz](frontend/README.md). R19–R21 siguen siendo evidencia del
visor Tabla; las regresiones del visor no se presentan como lectura desde chat.

## Verificación y hallazgos conservados

| Evidencia | Resultado y alcance |
| --- | --- |
| Acceso y regresión backend W02 | 57 PASS: grants, IO, concurrencia, texto, READ guardado y herramientas documentales. |
| Parser y consultas W03 | 84 PASS: parser compartido, planes y Decimal, con revisión independiente de límites y compatibilidad. |
| Interfaz W04 | 79 PASS: 30 CSV y 49 de regresión; TypeScript/Vite y comprobación de sintaxis PASS. |
| HTTP independiente W12 | 57 PASS: positivos y negativos, incluyendo STOP real mediante teamctl, comparación POST/GET/SQLite y hashes recalculados. |
| Navegador causal W04 | Chromium Linux, 1440×1000 y 390×844: PASS, datos reales y proveedor controlado, respuesta y referencias recuperadas tras recarga. |
| Demostración portable | [DEMO.json](closure/DEMO.json): PASS; sin grant devuelve 403, con grant analiza y persiste. Rechaza ejecución optimizada que desactivaría comprobaciones. |
| Suite completa de cierre | **1981 PASS, 2 SKIP**, además de 114 subtests satisfactorios; ejecutada realmente por `generate_dynamic_readme.py`, 231,952 segundos de pytest. [JUnit](closure/full-suite.xml). |
| README generado | Generación con suite completa PASS y `--check --skip-tests` PASS. La segunda orden comprueba consistencia y recoge casos; no vuelve a ejecutar la suite. |

Los conjuntos anteriores se solapan; no deben sumarse como número de pruebas
únicas. Los dos SKIP de la suite completa corresponden a reconocimiento WinRT
y al proceso CIM de Windows, no disponibles en Linux. La suite final utilizó
muestreo OTel `always_on` y una raíz de aplicación de prueba en `/tmp`, sin
`BAGO_DATA_ROOT` global. Recibos: [ejecución completa](closure/README_RUN_CHECK.json)
y [consistencia del README](closure/README_CHECK.json).

Se corrigieron antes de congelar código: la carrera P1 de revocación durante una
espera de política; límites numéricos y compatibilidad del parser; dos P2 de
cancelación y recuperación de revisión; y el menú Recursos recortado en móvil.
Las revisiones y los intentos fallidos se conservan en sus informes.

**Incidencia de entorno aún abierta:** una consulta móvil respondió revisión 2,
pero su GET posterior devolvió revisión 0 y ningún mensaje. Los ensayos con el
almacén existente observaron dos sustituciones de archivo SQLite por contenido
anterior en la carpeta compartida; el actor no está identificado. Con cerrar
conexiones no se resolvió. En `/tmp` pasaron 6/6 ensayos y 3.000 escrituras; allí
se realizaron la verificación causal de navegador y los casos HTTP finales.
Se conserva el FAIL original y no se parcheó `library.py`. El detalle y alcance
de esta conclusión están en [SQLITE_RUNTIME_INCIDENT.md](review/SQLITE_RUNTIME_INCIDENT.md).

La primera regresión completa también queda conservada: 30 FAIL, 1894 PASS y
2 SKIP. Veintiocho fallos de trazas se reprodujeron bajo el muestreo heredado del
1 % y dos pruebas de rutas recibieron un `BAGO_DATA_ROOT` global incompatible
con su comprobación del valor predeterminado. Tras corregir solo la configuración
de ejecución, los 157 casos de esos grupos pasaron. No se cambiaron código ni
expectativas del producto. Véase [environment-recheck.json](closure/environment-recheck.json).

## Reproducción

Instalar las dependencias de `requirements-test.txt` y usar un checkout con bytes
LF conservados para comparar las huellas de evidencia (por ejemplo,
`core.autocrlf=false`). Desde la raíz del repositorio:

```bash
python -m pytest -q tests/test_csv_chat_access.py tests/test_csv_query.py tests/test_csv_chat_flow.py
python scripts/demo_csv_chat.py --output demo_output/csv-chat.json
```

La demostración crea y elimina su propio directorio temporal; no utiliza los
almacenes del usuario. Para el navegador, abrir dos terminales:

```bash
python scripts/demo_csv_chat.py --serve
npm run dev --prefix frontend -- --host 127.0.0.1
```

El runner `frontend/tests/csv-chat/browser-f11.cjs` documenta las variables de
Playwright, URL y directorio nuevo de evidencia. Este servidor está etiquetado
como interpretación controlada; no es un despliegue ni una prueba de un modelo
real. El modo HTTP por defecto es suficiente para reproducir autorización,
lectura, cálculo y persistencia.

Los recibos gestionados y manifiestos de fuente permiten revisar qué se ejecutó
y qué archivos se verificaron. La identidad de misión del controlador acredita
coordinación; las huellas de fuentes y las ejecuciones aportan la evidencia del
producto. Ninguna de esas categorías sustituye a la otra.

La comprobación de preservación registra **211 archivos históricos** y confirma
que el expediente original, el runtime legacy, el canon, `local_rag.py` y
`library.py` no tienen cambios respecto de la base. Véase
[PRESERVATION.json](closure/PRESERVATION.json).
