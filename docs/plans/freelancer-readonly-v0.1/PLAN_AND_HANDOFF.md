# Freelancer — primera fase de lectura para BAGO5/ADL

Fecha: 2026-10-29. Estado: **CANDIDATO IMPLEMENTADO / INTEGRACION NATIVA PENDIENTE**.
No es una integración oficial publicada por Freelancer: es un adaptador propio de ADL para la API oficial.
No declarar la cuenta conectada ni el producto VERIFIED a partir de estos archivos.

## Mandato y frontera de entrega

El usuario ha solicitado construir una capacidad nativa para conectar su cuenta, consultar proyectos y leer conversaciones. Las ofertas y mensajes corresponden a una fase posterior con autorización explícita. No hay autorización para gastar saldo, contratar servicios, aceptar adjudicaciones, crear hitos, adjuntar archivos, publicar ni enviar mensajes. No se incluyen datos económicos personales del usuario en este repositorio público.

El objetivo final vive en la configuración y el chat existentes de ADL. Este incremento materializa el adaptador de lectura y sus pruebas, pero **no añade rutas, no registra herramientas de agente, no modifica pantallas y no toca la coordinación compartida**. Es una rama de revisión, no una release. La conexión y el acceso real a datos privados permanecen deshabilitados hasta completar los gates de host.

## Baseline inspeccionada

- Repositorio: `MarcValls/BAGO_AGENTIC_DATA_LAB`, `main`.
- Base inicial leída: `a9a4929fdbf51dd8872315de25ec8d277902c11c`, 2026-10-29 08:36:37 UTC.
- La PR #103 de esa base incorpora contratos SPEC_ONLY de Browser Bridge; no acredita un navegador operativo.
- Lecturas: `AGENTS.md`, protocolo de equipo, misión de referencia, rol coordinador, `src/connections/{service,security,transports}.py`, `src/api/connection_routes.py`.
- El intento de obtener un checkout completo mediante git falló por resolución DNS del entorno de trabajo. La consulta de fuentes por el conector GitHub sí funcionó. Las pruebas aquí son sobre una candidata parcial, no sobre una instalación completa de ADL.
- Releer `main` antes de integrar y comparar los archivos citados. No usar un worktree local antiguo como base.

## Reutilización y brechas

1. `ConnectionService` conserva registro y credenciales mediante `_secure_keyring`. Reutilizarlo: no almacenar tokens en prompts, repositorio, localStorage ni archivos de texto.
2. `src/connections/security.py:client_for` dispone de HTTPS, fijación DNS, rechazo de redirecciones, ausencia de proxies heredados, límites y transporte sin reintentos. El adaptador usa esa factoría en la ruta real; las pruebas de esta entrega inyectan un transporte falso.
3. `ConnectionService.invoke` y `GovernedMCPAdapter` ofrecen un recorrido con confirmación, permisos y recibos. **No son automáticamente la autorización nativa de un agente**. En los archivos leídos aparecen `confirmed`, efecto suministrado por el cliente y etiquetas `adl.local_user`. Revisar el middleware global y cerrar la vinculación principal/cuenta/proyecto/conversación/revisión antes de exponer la nueva capacidad. Este documento no declara vulnerabilidad global sin inspeccionar ese alcance.
4. El registro de conexiones persiste el resultado de una llamada en evidencia. No conectar mensajes privados a ese registro sin una política explícita de minimización, autorización de retención y borrado. Conservar identificadores/estado y evidencia necesaria; no copiar cuerpos de mensajes ni credenciales a logs por defecto. Un hash tampoco convierte datos privados en públicos.
5. Usar `frontend/src/components/ExternalConnections.tsx` y `src/api/connection_routes.py` como superficies candidatas. No abrir una nueva aplicación, otro gateway ni otro ledger.
6. Mantener Chat como orquestador. El modelo recibe datos remotos como contenido no fiable; no puede convertir un anuncio o mensaje en instrucciones, autorización ni gasto.

## Materializado en esta candidata

`src/connections/freelancer_readonly.py` implementa un transporte sin persistencia:

| Operación | Método y ruta fija | Alcance |
|---|---|---|
| `account.read` | GET `/api/users/0.1/self/` | ID, usuario y nombre visible; no saldo ni correo |
| `projects.search` | GET `/api/projects/0.1/projects/all/` o `active/` | Una página; `active_only` explícito, por defecto false |
| `project.read` | GET `/api/projects/0.1/projects/{id}/` | Un proyecto exacto y comprobación de ID de respuesta |
| `threads.list` | GET `/api/messages/0.1/threads/` | Metadata acotada; sin solicitar previews ni adjuntos |
| `messages.read` | GET `/api/messages/0.1/messages/` | Un hilo seleccionado, vinculado por `threads[]` y verificado en resultado |

Entornos fijos `sandbox` (por defecto) y `production`. Token OAuth en cabecera `Freelancer-OAuth-V1`, nunca en URL. No admite URL/método/headers libres. Esquemas cerrados y validación de tipos; máximo 20 elementos por página, offset 5000, timeout 20 s, respuesta 2 MiB. No paginación automática ni reintentos. IDs, presupuestos, moneda y estados remotos se conservan; no se calcula encaje ni se transforma `Awarded` en `Open`. Las medias de pujas no se presentan como presupuesto del cliente.

No hay `POST`, `PUT`, `PATCH` ni `DELETE` de Freelancer. Tampoco marcado explícito de mensajes como leídos. Los posibles efectos secundarios del GET en el servicio real necesitan comprobación live; no se deducen de una prueba simulada.

Errores 401/403/404/429, redirecciones, datos malformados, exceso de tamaño, credenciales reflejadas y resultados de otro hilo fallan sin devolver detalles sensibles. Cancelación se propaga. El adaptador **no emite permisos ni recibos de autoridad**, ni toma `approved=true` del modelo como permiso. Es un transporte interno que requiere un host confiable autorizado. No es una sandbox contra un proceso local malicioso.

## Estados y pruebas

- **IMPLEMENTADO:** construcción de solicitudes y transporte finito; proyección mínima de datos; errores sanitizados.
- **VERIFICADO LOCAL / DETERMINISTA:** pruebas con factoría falsa; sin red, usuario real ni credencial real. No equivalen a SDK live, al transporte DNS real o a aislamiento de cuenta probado en producción.
- **PROPUESTO:** enlace nativo de cuenta, configuración, asignación a agente y control desde chat.
- **NOT_RUN:** OAuth de navegador, revisión de scopes reales, keyring de Windows, API sandbox, API producción, pruebas de frontend, regresión completa de ADL, revisión independiente y gates de teamctl/README.
- **PROHIBIDO EN ESTA FASE:** ofertas, mensajería saliente, adjuntos, hitos, pagos y aceptación de proyectos.

`LOCAL_VERIFICATION.json` identifica hashes, entorno, comandos y resultados. `LOCAL_TESTS.log` conserva la salida local. El implementador ejecutó estas pruebas; no se afirma independencia del revisor.

## Plan nativo pendiente para Codex — no saltar controles

### P0. Identidad y coordinación

Releer `AGENTS.md` y protocolos actuales. Usar `teamctl.py` para la misión efectiva; no reiniciar, falsificar o sobrescribir `.bago/team/runtime/`. La misión por defecto leída corresponde al Decision Inspector y no se ha reetiquetado como Freelancer. Registrar una misión/scopes de Freelancer mediante el procedimiento vigente antes de empezar la integración compartida. Leer los roles requeridos. No afirmar READY/DONE sin el controlador y sus evidencias. Preservar el trabajo paralelo del usuario.

### P1. Contrato de cuenta y privacidad

Resolver token exclusivamente en backend con la infraestructura segura existente. Asociar referencia de credencial, entorno, usuario remoto esperado y revisión a la conexión del usuario. Configurado no significa conectado: mostrar verificado solo después de respuesta válida de `account.read`, con fecha y entorno. Sin credencial/permiso: UNCONFIGURED/DENIED; 401: reconectar; 403: no ampliar scopes automáticamente. Separar sandbox y producción incluso si el ID coincide. Revocar/rotar invalida selecciones, autorizaciones y lecturas pendientes. Revalidar al despachar y antes de publicar resultados de una petición que estaba en vuelo.

Esta entrega NO implementa OAuth Authorization Code/PKCE ni presume sus endpoints/scopes. El SDK oficial acredita el uso de un token OAuth2. Verificar en el portal oficial el procedimiento admitido y los permisos mínimos antes de implementarlos. El portal requiere JavaScript y sus detalles completos no pudieron inspeccionarse en esta sesión. Nunca solicitar la contraseña del usuario ni un token en el chat.

### P2. Conectar el transporte al recorrido existente

Incorporar un perfil finito de Freelancer al servicio de conexiones, no un puente genérico a cualquier endpoint. Clasificación READ propiedad del backend, no del modelo. Mantener autorización vinculada a operación/argumentos/cuenta/entorno/revisión; para mensajes, hilo exacto. No asumir que listar hilos autoriza leerlos todos ni enviarles mensajes. La membresía del hilo también debe ser aceptada por Freelancer. Actualizar la proyección de recibos sin duplicar autoridad ni guardar contenido privado por defecto. Confirmar errores y tiempos de espera sin convertirlos en éxito.

### P3. Configuración y chat

Extender la pantalla existente. Presentar entorno, estado y cuenta verificada, no token. Formularios con credencial de escritura solamente. Chat puede proponer búsqueda y lectura; configuración no otorga acceso automático a inbox. Presentar selector de hilo y alcance antes de recuperar mensajes. Leer únicamente páginas solicitadas. La UI debe marcar contenido remoto como datos no fiables. No habilitar salientes.

### P4. Verificar y demostrar

1. Repetir unitarios y regresión del servicio/router de conexiones. Ejecutar tests de acceso cruzado entre usuarios, proyectos, conversaciones y cuentas; revocación mientras la respuesta está en vuelo; reinicio sin credencial; fallo de keyring y fallo de persistencia de recibos.
2. Pruebas renderizadas y prueba real del recorrido Configuración -> cuenta -> proyecto -> hilo -> lectura, con IDs correlacionados. Evitar capturas públicas de mensajes privados.
3. Sandbox con credencial de sandbox introducida localmente: identidad, búsqueda, hilo y mensajes sintéticos existentes. Un inbox vacío no verifica la lectura de mensajes. No crear un hilo o mensaje de prueba en producción para completar el test.
4. Producción: una lectura por acción autorizada. Confirmar cuenta y proyecto; leer solo un hilo elegido por el usuario. No consumir una puja, marcar leído explícitamente, enviar ni pagar.
5. Ejecutar `python scripts/generate_dynamic_readme.py` y después `python scripts/generate_dynamic_readme.py --check --skip-tests`. No editar los README generados a mano. Gate global y `teamctl verify/close` según contrato. Hasta entonces, misión OPEN y no merge automático.

### P5. Escrituras posteriores, separadas

Enviar propuestas y mensajes requiere un diseño posterior: revisión del texto exacto, destinatario, hilo/proyecto, precio, moneda, plazo, adjuntos, cargos aplicables y autorización vinculada a esa revisión. Respetar las restricciones de comunicación de Freelancer. Ante timeout después del envío: estado incierto y reconciliación, no reintento ciego. No se autoriza implementar gastos ni enviar en esta entrega.

## Comandos y continuidad

Desde la raíz de la candidata:

```powershell
python -m unittest discover -s tests -p "test_freelancer_readonly.py" -v
python -m py_compile src/connections/freelancer_readonly.py tests/test_freelancer_readonly.py
```

Estos comandos no leen una cuenta ni necesitan token. No son la suite completa de ADL.
La integración debe partir de `origin/main` recién consultada o de esta rama rebasada y verificada. No copiar archivos sobre una carpeta con trabajo ajeno sin revisar el diff. Las únicas altas de esta candidata son el módulo, sus tests y esta documentación/evidencia. No hay instalación automática ni activación de capacidades.

## Fuentes primarias consultadas

Consultadas el 2026-10-29. Validan formas de API y límites de la afirmación, no una ejecución real:

- https://developers.freelancer.com/ — portal oficial; contenido interactivo no completamente legible.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/README.rst — OAuth2, sandbox y operaciones.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/session.py — cabecera OAuth.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/users/users.py — GET self.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/projects.py — search all/active y detalle.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/messages/messages.py — lectura de hilos/mensajes.
- https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/messages/helpers.py — filtros count y threads[].
- https://www.freelancer.com/support/project/messaging-on-projects — limitaciones de mensajería de la plataforma.

La implementación es propia; no incorpora el SDK LGPL ni copia sus módulos. No se verificó un contrato de tarifas de API; no se promete coste universal cero. En esta entrega no se llamó a la API ni se gastó saldo.

## Actualización de implementación nativa (2026-10-29)

Estado de esta candidata: **IMPLEMENTADO EN CÓDIGO / VERIFICADO LOCALMENTE CON DOBLES / CUENTA REAL Y GATE DE EQUIPO NOT_RUN**. La rama conserva el transporte de solo lectura de esta PR y añade las superficies de configuración/chat y la autorización vinculada a conversación. No es una publicación ni una validación con Freelancer real.

**Gate de arquitectura: NO_GO para producción y para declarar integración con la puerta común.** La ruta de lectura consume un reto propio y llama directamente a `FreelancerReadAdapter`; no despacha un permiso/efecto tipado por GEX ni usa su ledger. El reto local sirve como control de la candidata, pero no sustituye autorización humana durable. La comprobación de `Origin` es defensa CSRF/local y no autenticación ni aprobación humana. El inventario de Browser Bridge P0 deja GEX limitado a `fixture.read`; extenderlo requiere cerrar primero los contratos/versionado P1 y demostrar que esa fixture permanece intacta. No habilitar estas rutas en un runtime de producción hasta cerrar ese gate.

- Configuración usa el almacén seguro existente (`_secure_keyring`), conserva solo metadatos en el registro y no incluye el token en respuestas. El alta acepta un token OAuth ya emitido; el flujo OAuth Authorization Code/PKCE automático no está implementado.
- La verificación ejecuta `account.read`; solo una respuesta observada permite marcar la cuenta `connected`. Desconectar elimina la credencial local; no revoca el token en Freelancer.
- El chat permite únicamente `projects.search`, `project.read`, `threads.list` y `messages.read`. La propuesta de lectura muestra operación y argumentos antes de una segunda acción explícita. Los cuerpos remotos se presentan como contenido no fiable y no se guardan en recibos ni se envían a `/api/chat`.
- El reto es de un solo uso, limitado temporalmente y ligado a ID/revisión de conexión, cuenta, entorno, operación, argumentos y conversación activa. La cuenta Freelancer queda excluida de `discover` e `invoke` genéricos.
- Se añadió revalidación después del transporte: si cambian la conexión o la conversación durante la lectura, no se entrega el resultado privado al chat.

Verificación local sobre el candidato `codex/freelancer-native-integration-20261029` (base `a9a4929fdbf51dd8872315de25ec8d277902c11c`):

| Comprobación | Resultado |
|---|---|
| Pruebas focalizadas Freelancer y conexiones existentes | PASS, 66 tests + 92 subtests |
| Suite completa Python mediante `python scripts/generate_dynamic_readme.py` | PASS, 1765 tests |
| `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS; suite NOT_RUN por el modo `--skip-tests` |
| `npm test -- --run` | PASS, 820 tests en 88 archivos |
| `npm run test:ui` | PASS, 47 tests |
| `npm run build` | PASS; queda el aviso de bundle >500 kB |
| `py_compile` de archivos cambiados y `git diff --check` | PASS |

Pendiente y límites: no se usó cuenta/token real ni API sandbox/producción; no se hizo revisión visual en navegador; `teamctl` no pudo inicializar una misión nueva porque existe estado runtime legado, que se preservó. El flujo OAuth automático queda fuera de esta entrega. No declarar integración live ni gate terminal del equipo. Releer esta tabla si cambia el SHA candidato; las cifras pertenecen al estado verificado localmente.
