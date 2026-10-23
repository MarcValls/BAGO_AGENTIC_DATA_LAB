# Contacts Service 0.1.0 — contrato estable

Proyecto independiente; no importa BAGO, ADL ni servicios activos. Python >=3.11, biblioteca estándar. SQLite local, sin modificar Google. El adaptador ADL puede montar las mismas rutas. JSON UTF-8. El servidor standalone escucha únicamente 127.0.0.1 y exige X-Contacts-Key (secreto local generado al iniciar; no incluir en capturas). Las rutas Google no envían mensajes.

## Alcance fijado antes de implementar

C01 CRUD/search/revisión optimista y procedencia local. C02 vista previa inmutable e importación solo de IDs seleccionados, duplicados explícitos sin sobrescritura. C03 OAuth Desktop Google PKCE S256/state, callback loopback, alcance contacts.readonly, protección local de credenciales. C04 entradas CLI/API independientes y pruebas positivas, negativas y recuperación. Fuera: grupos, fotos, edición/borrado remoto, sincronización automática, envío, fusión automática, cuentas Workspace administradas.

## JSON y rutas, prefijo `/api/contacts/v1`

Contacto: `{id,name,phone,email,source,source_id,revision,created_at,updated_at}`. phone E.164 o vacío; email o vacío; name obligatorio; al menos phone/email. source local/google/fixture; revisión UUID opaca. Errores `{error:{code,message}}`; 400 validación, 404 inexistente, 409 revisión/duplicado, 401 clave, 503 Google no configurado/no conectado. No se devuelve token OAuth.

* GET `/contacts?q=...` → `{contacts:[Contacto]}` (búsqueda nombre/teléfono/email).
* POST `/contacts` body `{name,phone?,email?}` → 201 Contacto.
* GET `/contacts/{id}` → Contacto.
* PUT `/contacts/{id}` body `{name,phone?,email?,expected_revision}` → Contacto.
* DELETE `/contacts/{id}` body `{expected_revision,confirmed:true}` → `{deleted:true,id}`. Borra solo registro local; nunca Google.
* GET `/google/status` → `{configured,connected,state,scope,live_verified,last_error}`. connected significa token local vigente o renovable; `live_verified` solo tras respuesta Google en esta sesión almacenada. Sin token: disconnected; nunca fixture conectado.
* POST `/google/configure` body `{client_json_path}` → status. Ruta absoluta a JSON OAuth Desktop externo; copia protegida en raíz privada, no repositorio. Solo endpoints oficiales.
* POST `/google/connect` body `{}` → `{authorization_url,expires_at,callback_uri}`. Inicia listener loopback efímero y estado PKCE; UI abre authorization_url en navegador del usuario. Callback gestionado por listener dedicado; no callback arbitrario expuesto en servidor UI.
* POST `/google/disconnect` body `{confirmed:true}` → status. Elimina credencial local; no revoca/elimina datos de Google.
* POST `/google/preview` body `{}` → `{preview_id,revision,source,created_at,expires_at,contacts:[{selection_id,name,phone,email,source_id,duplicates:[{id,name}],warnings:[]}]}`. Lee conexiones paginadas Google People API. Preview dura 30 minutos, persiste para recuperación. Cada email/teléfono adicional se expone como fila seleccionable separada; no se inventa prefijo de país.
* POST `/imports/selected` body `{preview_id,expected_revision,selected_ids:[...],duplicate_policy:"skip"}` → `{imported:[Contacto],skipped:[{selection_id,reason}],preview_id}`. Selección vacía/ID ajeno/revisión caducada se rechazan. Solo skip; no merge/sobrescritura implícita. Repetición idempotente por identidad externa o phone/email normalizado.

CLI: `python contacts_service.py --root ROOT list|add|update|delete|google-status|google-configure|google-connect|google-preview|import-selected|fixture-preview|serve`. `--help` documenta argumentos. `fixture-preview --file FILE` admite People API JSON sintético etiquetado source=fixture, jamás conectado ni evidencia Google live.

## Aceptación y límites

Pruebas CLI sobre nuevas raíces: CRUD y reinicio; stale revision; duplicado; borrar sin confirmar; preview/import IDs seleccionados; ID ajeno; expiración; import repetido; Google sin configuración; PKCE/state; almacenamiento protegido y errores de persistencia. Tests OAuth/People con transporte fixture se identifican como simulación. Google real NOT_RUN hasta aportar OAuth Desktop JSON, habilitar People API y consentir desde cuenta propia. API visual ADL y capturas son responsabilidad del integrador; este paquete no produce fotos ni datos privados.

Referencias oficiales consultadas 2026-10-22: https://developers.google.com/identity/protocols/oauth2/native-app y https://developers.google.com/people/api/rest/v1/people.connections/list .
