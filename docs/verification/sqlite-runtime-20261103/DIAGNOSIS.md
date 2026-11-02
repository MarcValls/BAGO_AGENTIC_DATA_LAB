# Investigación de persistencia SQLite · 3 de noviembre de 2026

**Dictamen: causa y actor no identificados; persistencia NO REPARADA.**
La instrumentación y sus controles están comprobados. Esto no valida la instalación del usuario ni convierte los fallos anteriores en éxitos.

## Fuentes y base

Base recién recuperada: `6173ade56d64051b40586b80386faff79e22a119`, que integra la PR #115.
PR #116 examinada: `8b6e48b5cc9243b4884af90b5db876dba09ecc73`, abierta durante la investigación.
Se conservan sin modificar `docs/verification/csv-chat-20261101/`, el informe original y sus doce ensayos.

La evidencia nueva está en `.bago/goals/sqlite-runtime-20261103/`:
`implementation/` conserva resultados, pasos, diagnóstico comprimido, comparación de conexiones y fallos; `verification/` contiene la revisión independiente y sus controles. `source-manifest.json` identifica las fuentes finales de la instrumentación. Los recibos de coordinación identifican la implementación del controlador; los hashes del manifiesto identifican el código investigado. Ninguno autentica al sistema operativo.

El SHA-256 original de `audit_store_lifetime.jsonl` coincide:
`fdbfb77ea1a60e16f7065990a1ba36ea73056b88b3cdbe3ba1bf29748d2746db`.
El POST móvil conservado devuelve revisión 2 y dos mensajes; el GET posterior de la misma conversación devuelve revisión 0 y ninguno. Los ensayos originales 3 y 7 conservan su **FAIL**, con cambio de inode y recuperación de revisiones 168 y 369. La identidad del actor sigue desconocida. No se ha repetido aquí el recorrido móvil original.

## Qué cambia realmente la PR #116

`ConversationStore._connect()` usa `isolation_level=None`: las instrucciones individuales fuera de una transacción explícita se confirman automáticamente. `append_message()` usa `BEGIN IMMEDIATE` y `commit()` explícito. La PR #116 cambia seis contextos `with self._connect()` por `with closing(self._connect())`, sin cambiar estos mecanismos ni añadir restauraciones, sustituciones o comprobación de identidad física.

Un contraste directo retuvo las conexiones de `create`, `append_message` y `get`: las tres seguían utilizables después del contexto en `main`; en PR #116 las tres estaban cerradas. Ambas variantes devolvieron y recuperaron revisión 1 con un mensaje. **PASS para el cierre de recursos; reparación de las sustituciones NO DEMOSTRADA.** No se duplican aquí esos cambios de cierre ni se modifica la PR #116.

## Ensayos nuevos

Python 3.12.14; SQLite 3.53.1. Cada ensayo pasivo usa una base sintética nueva, un escritor de 500 mensajes, cuatro lectores y contraste después de cada escritura entre respuesta, `get` y otra conexión de solo lectura. Las ubicaciones actuales comparten dispositivo 27 y sistema `overlay`; no equivalen a dos medios físicos independientes ni reconstruyen exactamente el host anterior.

| Variante | `/tmp` | Directorio de trabajo |
| --- | --- | --- |
| `main` | 2 PASS | 2 PASS |
| PR #116 | 2 PASS | 1 PASS y 1 FAIL inicial; 3 PASS adicionales |
| Instrumentada | 2 PASS | 2 PASS |

En total, **14 ensayos PASS y un FAIL**, con 7.000 mensajes contrastados en los ensayos satisfactorios. No se observaron sustituciones espontáneas en esos catorce ensayos; esto no excluye que vuelvan a suceder.

El nuevo **FAIL** ocurrió en la consulta independiente final de la segunda repetición PR #116 en el directorio de trabajo: `sqlite3.DatabaseError: database disk image is malformed`. El ensayo inicial no manejó esa excepción final: perdió el resumen de ese caso, los pasos intermedios y la base al salir del directorio temporal. Se conserva el traceback íntegro y una declaración explícita de esa carencia en `attempt-01-failure.json`. **No hay evidencia suficiente para atribuir ese error a otra sustitución física.** El ensayo se reforzó para guardar pasos incrementales, registrar errores finales y conservar las bases sintéticas fallidas. Las repeticiones posteriores no cancelan este fallo.

Dos controles deliberados, ejecutados en procesos hijos identificados, restauraron una instantánea sintética después de seis escrituras confirmadas:

| Control | Persistencia | Diagnóstico |
| --- | --- | --- |
| Copia de instantánea y `os.replace` | FAIL esperado: revisión 0, cero mensajes | PASS: cambio de identidad y revisión inferior a la confirmada |
| Sobrescritura del mismo inode | FAIL esperado: revisión 0, cero mensajes | PASS: revisión inferior a la confirmada, sin falso cambio de inode |

Ambos devolvieron `integrity_check=ok`: integridad estructural no prueba actualidad. Los controles prueban detección de mecanismos conocidos, **no identifican el mecanismo histórico**. Los diarios JSONL se conservan comprimidos sin pérdida: para las rutas `diagnostics/*.jsonl` de los informes, abrir el archivo correspondiente con sufijo adicional `.gz`.

## Instrumentación limitada

Se activa exclusivamente inyectando `ConversationDiagnostics` en el constructor; el comportamiento predeterminado no crea registros ni modifica SQL. Ejemplo:

```python
from src.conversations.diagnostics import ConversationDiagnostics
from src.conversations.library import ConversationStore

observer = ConversationDiagnostics("/tmp/adl-diagnostics")
store = ConversationStore(database_path, diagnostics=observer)
try:
    # Ejecutar el recorrido autorizado que se quiere observar.
    pass
finally:
    observer.close()
```

Registra PID, hilo, tiempos, número de evento, identificadores HMAC por sesión, revisión/secuencia confirmadas y revisión/recuento recuperados, además de `stat` del archivo principal, journal, WAL y SHM. Señala cambio de dispositivo/inode, desaparición, retroceso de mtime y lecturas inferiores a escrituras confirmadas. La revisión no se equipara al número de mensajes.

No registra SQL, contenidos, títulos, referencias, propietarios, rutas ni identificadores de conversaciones en claro. El diario se crea con modo 0600 en POSIX; no se afirma una ACL equivalente en Windows. Máximo predeterminado: 20.000 eventos, con marca visible de agotamiento; memoria acotada a 1.024 confirmaciones y 64 identidades. Un fallo del observador no convierte una escritura confirmada en fallo de la aplicación. El propietario debe cerrar el observador.

Los `stat` observan la **ruta**, no el descriptor SQLite. Son muestras, pueden perder cambios entre muestras y no identifican al actor. La correlación vale para el mismo observador, no sobrevive al reinicio y puede perder entradas por los límites. No constituye un recibo resistente a restauraciones. Guardar el diario fuera del árbol sospechoso reduce exposición al mismo mecanismo, sin garantizar conservación. El diagnóstico añade E/S y altera tiempos: un PASS instrumentado no demuestra ausencia del fallo sin instrumentación.

## Atribución y sincronización

No se encontraron operaciones de sustitución en los métodos de conversación ejercitados ni en el adaptador de metadatos. El migrador portable sí usa copias y promoción de directorios, pero trabaja con un área de preparación y no se ejecutó en estos ensayos. El agente de sincronización del repositorio sustituye su propio recibo JSON. Estas observaciones no descartan cualquier otro proceso interno.

Se observaron procesos de infraestructura llamados `rsync`, `sync_share.sh` e `inotifywait`. La configuración legible de `/etc/rsyncd.conf` declara un módulo `scratch` sobre `/workspace/scratch`, escribible. `/usr/local/scripts/sync_share.sh`, SHA-256 `7a4b7aa2c2ee89eddb9b24fbe5267f4abd75a8cded4328773be9248d61cf3c32`, usa `--delay-updates`, `--update`, `--times` y no excluye SQLite. La observación se conserva separadamente en `environment-sync-observation.json`; se omiten credenciales y destinos.

**Hipótesis:** una transferencia de sincronización es compatible con sustitución y conservación de un mtime anterior. **No demostrado:** que ese proceso o un interlocutor externo transfiriera alguna de las bases afectadas. No hay enlace temporal/procesal que permita atribuir los incidentes. No se encontraron registros legibles en las dos ubicaciones de log comprobadas. `strace` no pudo iniciar la observación: `PTRACE_TRACEME: Operation not permitted`; se conserva su salida. Atribución por llamadas al sistema: **NOT_RUN**, no PASS.

No se cambiaron servicios de sincronización, exclusiones del host, bases reales, autorizaciones ni recibos de producto. No se aplica un parche especulativo de persistencia.

## Reproducción y estado

Desde una copia del repositorio con sus dependencias:

```sh
python -m pytest tests/test_conversation_diagnostics.py tests/test_conversation_library.py -q
python scripts/audit_sqlite_runtime.py --parent /tmp --output /tmp/adl-observed-01.jsonl --trials 3
python scripts/audit_sqlite_runtime.py --parent /ruta/compartida --output /tmp/adl-observed-02.jsonl --trials 3
python scripts/audit_sqlite_runtime.py --parent /tmp --output /tmp/adl-control-01.jsonl --trials 1 --messages 10 --injection replace
```

Para comparar otra versión, exportar su `library.py` y pasar `--source ruta/library.py`. No usar bases existentes: el script crea siempre una carpeta sintética. Los archivos de salida son exclusivos para impedir sobrescribir intentos anteriores. El código de salida cero significa recogida completada; el dictamen de cada ensayo está en `status`, incluyendo los controles que deben devolver FAIL. Las bases fallidas permanecen en `retained_fixture`; no se borran automáticamente.

La revisión independiente verificó los hashes, 21 tests centrados y tres controles adicionales: conversación confirmada que desaparece tras restaurar, retroceso de mtime sin pérdida y escrituras parciales del diario. **PASS en el alcance diagnóstico.** El cierre administrativo del equipo no implica validación del producto.

El resultado de la suite completa y del generador README se conserva con su alcance exacto en `CLOSURE.md`. Windows, la instalación real, el recorrido móvil original, los cambios en autorizaciones/recibos y la atribución al host permanecen **NOT_RUN**. P1 de producto abierto: persistencia susceptible de regresión observada sin causa atribuida. **NO_GO para declarar reparada la persistencia.**

Siguiente acción: ejecutar el diagnóstico en el entorno afectado con diario fuera del área sincronizada y auditoría de archivos habilitada por el administrador; correlacionar la identidad sustituida con un PID o transferencia antes de proponer la corrección mínima. Una nueva lectura correcta, por sí sola, no cierra la incidencia.
