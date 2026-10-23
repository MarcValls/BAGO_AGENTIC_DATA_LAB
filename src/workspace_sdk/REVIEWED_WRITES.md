# Escrituras revisadas AW-1

Este SDK amplía Workspace Service 0.1.0-RC1; ya no es byteidéntico a esa versión. Las tres primitivas adyacentes se conservan. La fuente anterior, hashes y parche se conservan en `docs/agent-write/evidence/AW02/`. No importa ADL, un proveedor ni su autenticación.

## API y CLI

`API(service).dispatch("POST", "/api/workspaces/v1/workspaces/{id}/actions", body)` y `workspace_service.py --parent PADRE action --workspace-id ID --json -` usan el mismo núcleo. Cada acción incluye `operation`: `prepare_write`, `review_write`, `revise_write` o `apply_write`.

Preparar requiere path, text, mode (`create`/`modify`) y context exacto con owner_kind=`agent`, owner_id, conversation_id, conversation_revision. Context es procedencia aportada por el consumidor, no autenticación del sistema operativo. Preparar y revisar conservan el destino; modificar conserva bytes/hash anteriores para revisión humana. El modelo recibe sólo un resumen, nunca el texto anterior por ese permiso.

Revisar recibe proposal_id y context; revisar no confirma. Cambiar texto requiere expected_revision y genera revisión y review_sha256 nuevos. El destino no puede cambiar: requiere otra propuesta. Aplicar acepta exclusivamente propuesta/revisión/review_sha256/context y confirmación exacta `{confirmed:true,operation:"apply_write",workspace_id,proposal_id,revision,review_sha256}`. No acepta texto/ruta/raíz nuevos.

## Estados y fallos

PROPOSED permite revisión; CONFLICT observa un cambio en la base y bloquea aplicar. APPLIED conserva recibo y una repetición devuelve ese recibo sin escribir. Antes del efecto se persiste intención durable bajo el mismo bloqueo del workspace. Si después falta persistencia/recibo, UNCERTAIN conserva o recupera la intención y observa el hash actual; nunca reintenta la escritura. `observation.matches_proposed` observa bytes, no prueba por sí solo quién los escribió ni sustituye un recibo. La revisión de recuperación sólo lee.

El estado se guarda en `.workspace-service/write-proposals`. Los fallos anteriores a persistir intención no autorizan un efecto. Si guardar el estado final falla, puede existir un recibo físico que aún no esté unido al estado; la recuperación conserva UNCERTAIN. No se inventa rollback.

## Límites

Raíz propietaria e identidad exacta, protecciones de rutas/enlaces/credenciales/tamaño UTF-8 y hashes previos se heredan del SDK. El bloqueo no es un sandbox frente a otros procesos capaces de reescribir todo el almacén. Una colisión externa entre comprobar y sustituir sigue siendo una frontera TOCTOU del sistema de archivos. Un usuario que controla todos los archivos puede recalcular hashes: integridad no equivale a autenticación.

El permiso de propuestas de Chat es por turno; la herramienta sólo prepara una propuesta y no puede confirmar/aplicar/ejecutar comandos. La carpeta activa debe coincidir exactamente con un workspace creado por el servicio bajo BAGO_WORKSPACE_PARENT; no se adopta una carpeta ajena. Pruebas deterministas no demuestran una inferencia real ni la revisión visual; esos gates corresponden a AW04/AW05.
