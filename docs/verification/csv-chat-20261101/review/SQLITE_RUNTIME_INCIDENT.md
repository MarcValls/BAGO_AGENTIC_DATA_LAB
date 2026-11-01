# Incidencia observada durante la verificación de persistencia

Estado: **observación de entorno conservada; actor de la sustitución no identificado**.
No se ha modificado `src/conversations/library.py` para ocultar o compensar esta incidencia.

## Observación inicial

La ejecución móvil de `../frontend/post-review-browser/mobile.json` obtuvo un
`POST /api/chat/control` HTTP 200 con `csv_analysis.status=answered`, revisión 2,
los dos mensajes y los resultados correctos del CSV histórico. La conversación
era `conv_556e4116cfdf495d92448dc469f36b47`. Al recargar y abrir esa misma
conversación, el mensaje no apareció. El GET directo posterior devolvió revisión
0, título `New conversation` y `messages=[]`; se conserva en
`../frontend/post-review-browser/mobile-persistence-diagnostic.json`.

La consulta independiente a SQLite con `mode=ro` confirmó la fila en revisión 0
y cero mensajes. `PRAGMA integrity_check` devolvió `ok`. El caso de navegador no
interceptaba endpoints ni sustituía respuestas de conversación. El fallo original
permanece **FAIL**: no se convirtió en PASS por el éxito de una repetición posterior.

## Contraste independiente

Se ejecutó `audit_store_lifetime.py` contra `ConversationStore` sin cambiar su
implementación. Cada caso creó una base temporal nueva: un escritor añadió hasta
500 mensajes, cuatro lectores hicieron `get`, `list`, lectura de metadatos del
historial y `gc.collect`. Después de cada escritura se contrastaron la respuesta,
un `get` nuevo y otra conexión SQLite de solo lectura. Se observaron `stat`
de la base; no se abrió el archivo de base de datos como bytes durante la prueba.

Una variante cerraba explícitamente todas las conexiones mediante una subclase
de `sqlite3.Connection` usada exclusivamente en el ensayo. La otra usaba el
comportamiento original. No hubo `VACUUM`, restauración, copia sobre la base,
`os.replace` o `rename` en el ensayo ni en los métodos de conversación ejercitados.

| Ubicación de las bases sintéticas | Casos | Resultado |
| --- | ---: | --- |
| `/tmp` | 6 | 6 PASS: 3.000 mensajes añadidos y contrastados; tres casos originales y tres con cierre explícito |
| Directorio de trabajo compartido | 6 | 4 PASS, 2 FAIL; ambos fallos también ocurrieron con cierre explícito |

Los dos fallos incluyeron una sustitución física del archivo de la base:

| Caso | Último estado correcto | Estado observado tras la escritura | Estado final independiente |
| --- | --- | --- | --- |
| 3 | revisión 208, inode 1975347, 102400 bytes | respuesta y `get` 209; inode 1975349, 81920 bytes; mtime retrocede | revisión 168, 168 mensajes |
| 7 | revisión 397, inode 1975397, 155648 bytes | respuesta y `get` 398; inode 1975402, 147456 bytes; mtime retrocede | revisión 369, 369 mensajes |

Los `ctime` avanzaron al mismo tiempo que los `mtime` retrocedieron. El cambio de
inode y la recuperación de contenido anterior acreditan una sustitución de
archivo durante estos ensayos. **No identifican quién la realizó ni prueban por
sí solos el mecanismo concreto que afectó al primer caso móvil.** La variante
con cierre explícito también falló; estos datos no justifican atribuirlo a las
conexiones no cerradas ni aplicar un parche especulativo al producto.

Evidencia íntegra: `audit_store_lifetime.jsonl`, 12 resultados, SHA-256
`fdbfb77ea1a60e16f7065990a1ba36ea73056b88b3cdbe3ba1bf29748d2746db`.
El script conservado contiene las rutas exactas del entorno en el que se ejecutó.
Python observado: 3.12.14; SQLite: 3.53.1.

## Decisión de verificación

El backend de QA se reinició con las mismas fuentes y con proyecto, permisos y
base SQLite sintéticos en `/tmp/adl-csv-browser-fixture-20261101`. La ejecución
causal de navegador de W04 verificó escritorio y móvil, GET de la conversación
exacta después de recargar, referencias persistidas, hash del servidor cargado
y estabilidad del inode de SQLite. Sus resultados están en
`../frontend/causal-browser/` y en `../frontend/W04-HANDOFF.json`.

Los casos HTTP independientes de W12 también usan `/tmp` para el estado mutable.
Esta elección aísla la condición observada; no demuestra que el entorno compartido
sea incapaz de volver a sustituir otros archivos, ni constituye una reparación de
la instalación del usuario. La instalación real y Windows siguen **NOT_RUN**.
Las evidencias originales del recorrido de 38 minutos y los fallos de esta QA se
preservan por separado de las ejecuciones que sí finalizaron correctamente.
