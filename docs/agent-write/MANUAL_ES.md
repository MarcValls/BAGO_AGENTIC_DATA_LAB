# BAGO ADL · Archivos propuestos y escritura revisada

[Manual general](/manual) · [Guía de escritura revisada](/manual/escritura-revisada)

Guía española de la candidata `agent-chat-write-20261023`. Describe la preview preparada con frontend Docker en **http://127.0.0.1:8093** y API del host en **http://127.0.0.1:8094**. El SDK de archivos declara **0.2.0-RC1**. No es una declaración de entrega final: Docker definitivo, regresiones completas y gate de cierre tienen evidencias separadas.

## Índice

- [Abrir la preview y reconocer la sesión](#abrir-la-preview-y-reconocer-la-sesion)
- [Elegir un proyecto donde se pueda escribir](#elegir-un-proyecto-donde-se-pueda-escribir)
- [Pedir una propuesta desde Chat](#pedir-una-propuesta-desde-chat)
- [Revisar, editar y confirmar](#revisar-editar-y-confirmar)
- [Entender estados y recuperar una revisión](#entender-estados-y-recuperar-una-revision)
- [Inspeccionar la ejecución actual](#inspeccionar-la-ejecucion-actual)
- [Usar el SDK y la CLI sin la aplicación](#usar-el-sdk-y-la-cli-sin-la-aplicacion)
- [Arranque de administración de esta preview](#arranque-de-administracion-de-esta-preview)
- [Evidencias existentes y límites](#evidencias-existentes-y-limites)

## Abrir la preview y reconocer la sesión

1. Abre **http://127.0.0.1:8093**. Ese enlace presenta el frontend actual de L mediante Docker.
2. La aplicación llama a `/api` en el mismo origen; el proxy lo lleva al backend8094. `/manual` y `/ws` también se encaminan a ese backend. Para trabajar desde la interfaz conserva el enlace8093; no cambies a otra instalación por su parecido visual.
3. El proveedor se conserva en el host mediante la referencia a la configuración existente de I y el almacén de credenciales del sistema operativo. Esta preview no pide copiar tokens ni volver a registrar el mismo proveedor para usar otra pantalla.
4. Los datos permanecen en `R/.bago/goals/integrated-services-20261023/preview-ui-01`, fuera del contenedor frontend: conversaciones, perfiles, proyectos, Contactos, Comunicaciones y evidencias. Reiniciar el frontend no autoriza borrar esos datos.

R es el repositorio principal `C:/Users/AMTEC_Terminal_1º/Desktop/BAGO5_ADL`; L es su carpeta `.worktrees/agent-chat-write-20261023`; I es `.worktrees/integrated-services-20261023`.

## Elegir un proyecto donde se pueda escribir

Una carpeta seleccionada para lectura no queda adoptada automáticamente como proyecto gestionado.

1. Abre **Workspace** y su área **Proyectos**.
2. Selecciona un proyecto creado por el servicio. Para una prueba nueva, indica un nombre y título nuevos, pulsa **Revisar creación**, comprueba la carpeta padre, marca la confirmación y pulsa **Confirmar y ejecutar**. Crear el proyecto sí crea su carpeta y los documentos iniciales de contexto, estado y continuidad.
3. En el proyecto elegido, pulsa **Usar este proyecto en ADL** y confirma la selección cuando aparezca la revisión.
4. Comprueba la ubicación del proyecto. El backend acepta propuestas de archivos sólo si la carpeta activa coincide con un proyecto propietario bajo la carpeta padre configurada.

Si aparece `workspace_parent_required`, falta configurar la carpeta padre. Si aparece `workspace_not_owned`, la carpeta activa no es uno de esos proyectos. No intentes solucionarlo copiando manifiestos a una carpeta ajena.

## Pedir una propuesta desde Chat

1. Abre **Chat**, elige un agente guardado y su conversación. El permiso de archivos corresponde al agente seleccionado, no al asistente global.
2. Marca **Proponer archivos** para ese mensaje.
3. Escribe una petición concreta. Ejemplo: «Propón crear `resumen-prueba.md` con tres puntos sobre esta tarea. Quiero revisar el contenido antes de escribirlo».
4. Pulsa el botón de enviar. El permiso se consume en ese turno y la casilla vuelve a desmarcarse.
5. Busca la tarjeta **Crear archivo** o **Modificar archivo**. Una frase del modelo que diga “archivo creado” no sustituye esa tarjeta ni un recibo.

**Preparar una propuesta no modifica el archivo destino.** El modelo sólo dispone de la herramienta `propose_workspace_write` con ruta relativa, texto y modo crear/modificar; no puede confirmar, aplicar, ejecutar comandos ni elegir otra raíz.

La lectura web y la lectura local son permisos independientes. Para utilizar páginas públicas, marca además el permiso web, introduce las URL HTTPS y comprueba sus orígenes. Para enviar contenido de archivos existentes al modelo, autoriza expresamente la lectura local de sus rutas. El permiso de proponer una modificación no entrega al modelo el contenido anterior del archivo.

Se permite una propuesta de archivo por turno. La respuesta de un proveedor puede fallar después de haber preparado una propuesta: si la tarjeta permanece junto a un mensaje fallido, el archivo todavía necesita revisión y confirmación. No supongas que una respuesta fallida borró la propuesta ni que escribió el archivo.

## Revisar, editar y confirmar

1. Comprueba **Proyecto** y **Archivo** en la tarjeta. Un proyecto nuevo y un archivo nuevo son operaciones distintas.
2. Lee la pestaña **Contenido**. En **Cambios**, revisa la diferencia y, si procede, despliega **Contenido anterior**.
3. Para corregir el texto, edita **Contenido propuesto** y pulsa **Guardar propuesta y revisar**. Eso guarda una revisión de la propuesta, sin escribir el destino.
4. Vuelve a revisar los cambios guardados. Cada edición cambia revisión y huella; una confirmación anterior no vale para el texto nuevo. Mientras hay edición sin guardar, la escritura está deshabilitada.
5. Marca **He revisado el proyecto, el archivo y el contenido de esta revisión** sólo cuando estés de acuerdo.
6. Pulsa **Confirmar y escribir**. Esa es la acción que puede escribir el archivo. La confirmación incluye exactamente proyecto, propuesta, revisión y huella revisados; no permite sustituir la ruta o el texto al confirmar.
7. Espera el estado. Si muestra **Aplicada**, revisa el recibo y comprueba el archivo por una observación independiente, por ejemplo desde el explorador de archivos o el SDK.

Para no escribir, deja la casilla sin marcar y no pulses la acción final. La tarjeta no ofrece un estado de cancelación persistente: cerrar la pantalla o salir de la conversación deja la propuesta guardada, sin aplicarla. No se declara cancelada una escritura que ya ocurrió.

## Entender estados y recuperar una revisión

| Estado/código | Qué significa | Qué hacer |
|---|---|---|
| `PROPOSED` · Propuesta pendiente | Existe una propuesta durable; el destino no se ha aplicado por ese flujo. | Revisar, guardar cambios de propuesta si los hay y confirmar expresamente. |
| `APPLIED` · Aplicada | El servicio registra aplicación y recibo de esa revisión. | Consultar recibo y archivo. Reabrir o repetir la misma confirmación devuelve el resultado existente; no vuelve a escribir. |
| `CONFLICT` · Conflicto de revisión | El archivo/base cambió o desapareció respecto de lo revisado, o la propuesta ya no coincide. | Revisar la situación actual. Preparar una propuesta nueva cuando cambie el alcance; no forzar una revisión antigua ni restaurar hashes a mano. |
| `UNCERTAIN` · Resultado incierto | Se persistió intención y no puede acreditarse un resultado completo. El archivo puede haber cambiado. | No repetir la escritura. Consultar la observación de hash/recibo y conservar evidencia; revisar el archivo sin modificarlo y resolver la incidencia. Coincidir con el hash propuesto no prueba por sí solo quién escribió ni sustituye un recibo. |
| `busy` · HTTP409 | Otro proceso mantiene el bloqueo del mismo proyecto. | Esperar a que termine la operación conocida y pulsar **Recargar revisión**, que sólo lee. No borrar el archivo de bloqueo ni automatizar reintentos de escritura. |
| Error503 al cargar revisión | La revisión no pudo recuperarse; puede ser una incidencia de persistencia o transporte. | Conservar el error y recargar la revisión expresamente cuando el servicio esté disponible. No confirmar con una revisión no cargada ni interpretar el error como rollback. |
| Revisión obsoleta / `proposal_revision_conflict` | Otra edición cambió la revisión o la huella de la propuesta. | Recargar, comprobar el contenido actual y confirmar de nuevo sólo si corresponde. |

### Reiniciar o recargar

Las propuestas se conservan bajo `.workspace-service/write-proposals` en el proyecto propietario. Al recuperar una conversación, la tarjeta carga la revisión actual de la misma propuesta. Esa consulta nunca es una autorización de escritura.

- Una propuesta aplicada debe mostrar su recibo, sin ejecutar otra escritura.
- Una intención sin final se observa como `UNCERTAIN`; reiniciar no la reintenta.
- Una propuesta editada puede tener una revisión más nueva que el resumen original del mensaje. La tarjeta conserva proyecto/ruta/contexto y utiliza la revisión actual al confirmar.
- Cambiar de agente o conversación invalida la selección anterior de la tarjeta. No uses una revisión asociada a otro interlocutor.

Hubo un fallo real previo de restauración automática503. La recuperación explícita se documentó por separado; la causa exacta del primer503 quedó **INCONCLUSIVE**. Después se repararon dos mecanismos reproducibles: el bloqueo de lectura de un byte en Windows se mapea a `busy`, y el montaje de revisión se ajustó para StrictMode. La evidencia posterior registra recuperación automática con el archivo sin cambios; no reescribe el fallo original como éxito ni garantiza cualquier reinicio/entorno.

## Inspeccionar la ejecución actual

Abre **Inspect** desde la barra lateral o desde el mensaje que quieras revisar. El acceso desde un mensaje conserva su ejecución concreta. El acceso general abre Decision Inspector con la ejecución más reciente de la conversación actual; no necesitas elegir una para empezar. El selector permite consultar las anteriores de esa misma conversación.

Si todavía no hay ejecuciones registradas, se muestra **Sin ejecución registrada** y los contadores de registros a cero. No se crea una traza ficticia para llenar esa pantalla. Las conversaciones anteriores que no guardaron referencias de traza permanecen en ese estado; los turnos nuevos completados por el asistente sí registran su traza de control.

Los contadores distinguen ejecuciones, eventos, referencias y registros de autorización. Un registro de autorización no significa que todas las acciones estén permitidas. Resumen, trazas, evidencias, autorización y evaluación muestran sus datos correspondientes; si no se produjo un paquete de autorización o una evaluación, se indica su ausencia. No se deduce una evaluación PASS a partir de COMPLETED ni una autorización a partir de ALLOW.

Si la ejecución más reciente tiene evidencia ausente o inválida, Inspect mantiene ese aviso en lugar de sustituirla por una anterior que hubiera pasado. La demo histórica sólo se abre mediante su opción explícita, identificada como independiente del chat. Las vistas globales de trabajos y efectos conservan su indicación de alcance global.

El código y la API de este recorrido tienen pruebas separadas en `docs/agent-write/evidence/AW04/inspect-repair/`. La comprobación visual final, incluida la interfaz bilingüe, se registra después de integrar sus cambios; esta explicación no sustituye esa evidencia.

## Usar el SDK y la CLI sin la aplicación

La CLI real es `src/workspace_sdk/workspace_service.py`, versión declarada0.2.0-RC1. Se ejecuta con Python y sus módulos adyacentes `reused_primitives.py`, `sync_primitives.py` y `auth_primitives.py`. No necesita ADL, un proveedor ni un modelo para preparar/revisar/aplicar sobre una carpeta propietaria local. Los comandos siguientes son instrucciones reproducibles; **no se han ejecutado al redactar esta guía**.

### 1. Preparar una carpeta de prueba nueva

Ejemplo PowerShell desde cualquier carpeta. Cambia las rutas del ejecutable/SDK si instalas el SDK aparte. En esta preview, el Python existente está en I.

```powershell
$BagoRepo = 'C:\Users\AMTEC_Terminal_1º\Desktop\BAGO5_ADL'
$BagoCandidate = Join-Path $BagoRepo '.worktrees\agent-chat-write-20261023'
$BagoPython = Join-Path $BagoRepo '.worktrees\integrated-services-20261023\.venv\Scripts\python.exe'
$BagoSdk = Join-Path $BagoCandidate 'src\workspace_sdk\workspace_service.py'
$BagoParent = Join-Path 'C:\BAGO_ADL_TESTS' ('manual-write-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $BagoParent | Out-Null
& $BagoPython -B $BagoSdk --parent $BagoParent --help
$BagoWorkspace = (& $BagoPython -B $BagoSdk --parent $BagoParent create --name manual --title 'Prueba manual' --confirmed) | ConvertFrom-Json
$BagoWorkspace.id
```

Resultado esperado: un ID `workspace_...`, carpeta `manual` nueva y sus tres documentos de contexto. `create --confirmed` autoriza esa creación; no se adopta una carpeta ya existente. Conserva la fixture para revisar sus evidencias.

### 2. Guardar una propuesta, sin escribir su destino

```powershell
$BagoContext = @{ owner_kind='agent'; owner_id='manual-fixture'; conversation_id='manual-turn'; conversation_revision=0 }
$BagoPrepareFile = Join-Path $BagoParent 'prepare.json'
@{
  operation='prepare_write'; path='resultado.txt'; text="Resultado revisado.`n"
  mode='create'; context=$BagoContext
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $BagoPrepareFile -Encoding utf8
$BagoProposal = (& $BagoPython -B $BagoSdk --parent $BagoParent action --workspace-id $BagoWorkspace.id --json $BagoPrepareFile) | ConvertFrom-Json
$BagoProposal.status
Test-Path -LiteralPath (Join-Path $BagoWorkspace.root 'resultado.txt')
```

Resultado esperado: `PROPOSED` y `False`. El contexto de esta CLI es procedencia aportada por el consumidor; no autentica una sesión de ADL ni concede por sí solo acceso al sistema operativo.

### 3. Revisar desde otra invocación

```powershell
$BagoReviewFile = Join-Path $BagoParent 'review.json'
@{ operation='review_write'; proposal_id=$BagoProposal.proposal_id; context=$BagoContext } |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $BagoReviewFile -Encoding utf8
$BagoReview = (& $BagoPython -B $BagoSdk --parent $BagoParent action --workspace-id $BagoWorkspace.id --json $BagoReviewFile) | ConvertFrom-Json
$BagoReview | Select-Object workspace_id,path,mode,status,revision,before_sha256,proposed_sha256,review_sha256
$BagoReview.proposed_text
$BagoReview.diff
```

Resultado esperado: misma propuesta durable, revisión/hash y contenido revisables, sin archivo destino. Para modificar un archivo existente prepara otra propuesta con `mode='modify'`; el SDK observa y conserva su base. El cliente no inventa el hash previo.

Para editar una propuesta pendiente, el cuerpo de la acción es:

```json
{
  "operation": "revise_write",
  "proposal_id": "ID_DE_LA_PROPUESTA",
  "expected_revision": "REVISION_ACTUAL",
  "text": "Nuevo texto revisable",
  "context": {
    "owner_kind": "agent", "owner_id": "manual-fixture",
    "conversation_id": "manual-turn", "conversation_revision": 0
  }
}
```

Guárdalo en otro archivo y usa el mismo comando `action --json RUTA`. Revisa después su respuesta completa; no confirmes con `$BagoReview` viejo. Una ruta distinta necesita una propuesta nueva.

### 4. Confirmar exactamente la revisión leída

Sólo continúa si has revisado los datos y `status` sigue siendo `PROPOSED`. Este bloque realiza la escritura; la frase local evita ejecutarlo inadvertidamente al seguir la guía.

```powershell
if ($BagoReview.status -ne 'PROPOSED') { throw 'Revisa el estado antes de confirmar.' }
if ((Read-Host 'Escribe ESCRIBIR para confirmar esta revisión') -cne 'ESCRIBIR') { throw 'Sin confirmación: no se aplicó la propuesta.' }
$BagoApplyFile = Join-Path $BagoParent 'apply.json'
@{
  operation='apply_write'; proposal_id=$BagoReview.proposal_id
  expected_revision=$BagoReview.revision; review_sha256=$BagoReview.review_sha256
  context=$BagoContext
  confirmation=@{
    confirmed=$true; operation='apply_write'; workspace_id=$BagoReview.workspace_id
    proposal_id=$BagoReview.proposal_id; revision=$BagoReview.revision
    review_sha256=$BagoReview.review_sha256
  }
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $BagoApplyFile -Encoding utf8
$BagoApplied = (& $BagoPython -B $BagoSdk --parent $BagoParent action --workspace-id $BagoWorkspace.id --json $BagoApplyFile) | ConvertFrom-Json
$BagoApplied | ConvertTo-Json -Depth 12
if ($BagoApplied.status -eq 'APPLIED') {
  Get-Content -LiteralPath (Join-Path $BagoWorkspace.root 'resultado.txt')
  Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $BagoWorkspace.root 'resultado.txt')
}
```

Resultado esperado positivo: `APPLIED`, recibo con `after_sha256`, archivo con el texto revisado y SHA-256 coincidente. Si devuelve `UNCERTAIN`, no vuelvas a ejecutar apply: usa `review_write` para observar y conserva el resultado. Un código de salida0 de la CLI no convierte `UNCERTAIN` en éxito.

La CLI ofrece además `list`, `github-read` y otras acciones locales existentes. `github-read` depende de GitHub CLI/autenticación y no forma parte de esta prueba de archivos. Códigos de salida:0 devuelve resultado JSON;2 devuelve ServiceError;3 indica fallo de operación. No confundir `--json -` (entrada estándar) con una herramienta distinta: es el mismo dispatcher SDK.

## Arranque de administración de esta preview

Estas instrucciones requieren la preview ya preparada: DATA/SEED existente, I con su Python/dependencias/configuración local, Docker Desktop y el bundle `docs/agent-write/runtime/docker-8093`. No son un instalador de producción. Antes de arrancar comprueba con quien administra la sesión si8093/8094 ya están en uso; no cierres otra instalación para liberar puertos.

En una terminal, deja el backend del host ejecutándose:

```powershell
& $BagoPython -B (Join-Path $BagoCandidate 'docs\agent-write\runtime\serve_preview.py')
```

En otra terminal, prepara las mismas variables de rutas del primer bloque y ejecuta el bundle explícito:

```powershell
$BagoDockerBundle = Join-Path $BagoCandidate 'docs\agent-write\runtime\docker-8093'
$env:BAGO_DEV_CANDIDATE = 'review-live-20261023'
$env:BAGO_DEV_FRONTEND_PORT = '8093'
docker compose --project-name bago-review-8093 --project-directory $BagoDockerBundle -f (Join-Path $BagoDockerBundle 'compose.yaml') -f (Join-Path $BagoDockerBundle 'compose.live.yaml') --profile dev build frontend
docker compose --project-name bago-review-8093 --project-directory $BagoDockerBundle -f (Join-Path $BagoDockerBundle 'compose.yaml') -f (Join-Path $BagoDockerBundle 'compose.live.yaml') --profile dev up -d --wait frontend
```

Se montan sólo `frontend/src` y `frontend/public` de L en lectura; dependencias frontend usan un volumen Docker. El proxy conserva Host/Origin y permite explícitamente los orígenes locales8093/8094. El backend conserva DATA y la referencia al proveedor en el host. El launcher genérico `dev.py` no incluye por sí solo `compose.live.yaml`: no lo uses como sustituto de este arranque identificado.

Health200, build o carga de la interfaz no demuestran por sí solos una inferencia, una escritura ni la conservación del estado tras un error de HMR. Las pruebas finales de Docker se registran por separado.

## Evidencias existentes y límites

Esta guía se redactó leyendo fuentes y registros, sin volver a ejecutar sus pruebas ni generar inferencias. Cada resultado pertenece a su candidato y a su momento:

| Registro | Alcance acreditado por ese registro |
|---|---|
| `evidence/AW02/handoff.json` y `attempt03/RESULT.json` | Propuestas durables y controles;127 pruebas focales y19 del SDK externo en aquella fase. La exclusión histórica de identidad se conservó y se trató después como derivación, no como PASS implícito. |
| `evidence/AW04/integration-repair-01/RESULT.json` |143 pruebas backend y41 frontend focales; adaptadores de proveedor simulados y derivación SDK, sin inferencia real atribuida a esos tests. |
| `evidence/AW04/live-write/FILESYSTEM_OBSERVATION.json` | Observación independiente del archivo tras confirmación UI real:37bytes y SHA-256 `c3205dc09fb8848dac34fe1764a3a33e1bab1160a97f7f78e0356b9ae4082884`. No se ha repetido al redactar la guía. |
| `evidence/AW04/live-write/RECOVERY_AND_CORRELATION.json` | Recuperación explícita APPLIED y correlación local/Jaeger; conserva primer fallo automático como FAIL y causa INCONCLUSIVE. Jaeger acredita spans de modelo/propuesta, no la escritura posterior por sí solo. |
| `evidence/AW04/recovery-review/REPORT.md` | Diagnóstico y reproducción focal del bloqueo Windows; distingue mecanismo demostrado de causa histórica no acreditada. |
| `evidence/AW04/lock-repair-01/RUNTIME_RESULT.json` | Recuperación automática posterior en Windows/backend reparado y frontend Docker actual, con hash/mtime del archivo conservados. No garantiza todas las plataformas ni reescribe el primer fallo. |
| `runtime/docker-8093/REVIEW.json` | Revisión estática/config de mounts, proxy, paquetes y hashes; las pruebas HTTP/WS/HMR reales necesitan sus propios recibos. |

No se suman repeticiones ni fases para formar una cifra global de tests. Esta guía no afirma cierre del goal, Docker final validado, entrega/instalación general, Windows y Linux equivalentes ni envío WhatsApp. Los mensajes/recibos/trazas conservan su contenido original; una futura traducción de interfaz no debe reescribirlos.
