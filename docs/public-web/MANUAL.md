# Manual de uso de BAGO ADL

Guía para trabajar desde el chat y las pantallas de BAGO. Abre una sección según lo que necesites hacer. Las explicaciones y detalles técnicos están aquí para que las pantallas puedan mostrar primero tu tarea.

## Contenido

- [Orientarse y empezar](#orientarse-y-empezar)
- [Chat y lectura de páginas públicas](#chat-y-lectura-de-páginas-públicas)
- [Revisar fuentes y ejecuciones](#revisar-fuentes-y-ejecuciones)
- [Agentes](#agentes)
- [Proyectos, archivos y contexto](#proyectos-archivos-y-contexto)
- [Git local y planes de GitHub](#git-local-y-planes-de-github)
- [Contactos e importación de Google](#contactos-e-importación-de-google)
- [Vincular WhatsApp](#vincular-whatsapp)
- [Preparar mensajes y programarlos](#preparar-mensajes-y-programarlos)
- [Experimento de lectura y revisión](#experimento-de-lectura-y-revisión)
- [Si algo no funciona](#si-algo-no-funciona)
- [Información para administración e integración](#información-para-administración-e-integración)

## Orientarse y empezar

La barra lateral permite cambiar entre Chat, Comunicaciones, Contactos, Workspace y Agentes. Settings reúne las conexiones y preferencias. Inspect abre la revisión de una ejecución. Manual abre esta guía en otra pestaña.

**Los bloques con flecha se pueden desplegar.** Pulsa su cabecera para ver más información y vuelve a pulsarla para recogerla. También puedes llegar con la tecla Tab y abrirlos con Enter o Espacio. El contorno resalta el control seleccionado con el teclado.

Las pestañas superiores separan las áreas de una pantalla. Puedes pulsarlas o usar Tab y las flechas izquierda/derecha; Inicio y Fin llevan a la primera y última. Cambiar de pestaña conserva lo que estabas editando.

Los cambios que necesitan revisión muestran primero una propuesta o un borrador. Lee los datos, marca la confirmación y pulsa la acción final cuando estés de acuerdo. Un borrador guardado no significa que se haya enviado un mensaje ni ejecutado una operación.

## Chat y lectura de páginas públicas

1. Abre **Chat** y elige una conversación. Puedes usar el asistente de la aplicación o un agente guardado en **Conversations and agents**.
2. Elige el modelo disponible para ese interlocutor. Si no hay ninguno, configura el proveedor en Settings.
3. Escribe lo que quieres obtener, con una tarea concreta. Por ejemplo: «Resume los servicios descritos en esta página y cita las fuentes que hayas leído».
4. Si necesitas consultar la web, marca **Permitir lectura web pública**.
5. Pega una o varias URL HTTPS en **URL HTTPS de entrada · una por línea**. Se admiten hasta ocho entradas distintas. Revisa los orígenes que aparecen debajo.
6. Pulsa **Send**. El permiso vale para ese turno, esa conversación y ese interlocutor. La casilla vuelve a quedar desmarcada.

Ejemplo de entrada pública: `https://www.sollutia.com/es/empresa.html`. La disponibilidad de la página depende de su servidor.

El permiso permite leer páginas de los orígenes indicados. Una URL de entrada no autoriza por sí sola otros dominios a los que enlace. El lector rechaza credenciales, destinos locales o privados y redirecciones fuera del alcance autorizado. No ejecuta los scripts de las páginas ni inicia sesión en ellas. Una página que necesita JavaScript o acceso privado puede no aportar el contenido que buscas.

**Lectura local:** la casilla **Allow project file reads** es un permiso independiente. Si la necesitas, indica las rutas relativas exactas de los archivos del proyecto. Marcar lectura web no concede lectura de archivos; ambos permisos pueden utilizarse expresamente en el mismo turno.

El texto de una página puede contener instrucciones ajenas a tu tarea. Se trata como fuente externa, no como una orden tuya. Comprueba las afirmaciones antes de usarlas como resultado para un cliente.

## Revisar fuentes y ejecuciones

Después de una respuesta, despliega **Fuentes web** o **Archivos consultados** para ver las referencias conservadas. Una respuesta sin fuentes registradas no demuestra que se haya leído una página o un archivo.

En las fuentes web puedes consultar:

- URL solicitada y URL final.
- Fecha y hora de captura en UTC.
- Huellas SHA-256 del contenido original, del texto y del manifiesto.
- Identificador de la captura guardada, llamado snapshot.

La huella es un identificador del contenido. Sirve para contrastar que una copia sigue siendo la misma; no demuestra que el contenido sea verdadero.

**Lecturas** muestra el resultado registrado. `ALLOW` indica una lectura admitida; `DENY`, una denegación; `FAIL`, un fallo. Si hay una incidencia, aparece en la cabecera del bloque. El detalle conserva el motivo.

Pulsa **Inspeccionar ejecución** junto a la respuesta para abrir su traza. También puedes desplegar **Detalles de la traza** para consultar sus identificadores y, cuando exista, el enlace de Jaeger. Una traza es un registro de lo ocurrido; no sustituye la revisión del resultado.

Inspect distingue **Conversación actual** de **Demo histórica**. La demo no es una ejecución nueva ni pertenece a la conversación por el hecho de estar visible. Los historiales globales de Jobs o BER aparecen identificados como independientes. Si no hay artefactos para una conversación, ese estado debe permanecer explícito.

## Agentes

En la barra lateral, despliega **Agentes** y abre **Mis agentes**. Busca por nombre, descripción, tipo o identificador.

- **Crear agente** prepara un perfil nuevo. Revisa su tarea, proveedor, modelo y herramientas antes de guardarlo.
- **Editar** modifica un perfil existente. No necesitas crear otro perfil para cambiarlo.
- **Probar tarea** abre el recorrido de pruebas del agente seleccionado.
- **Evaluar** abre el laboratorio de evaluación con ese mismo agente.
- **Eliminar perfil** muestra primero una revisión. Confirma sólo después de comprobar qué perfil vas a quitar.

La eliminación de un perfil conserva sus conversaciones, trazas, evaluaciones y ejecuciones, y mantiene una copia local para recuperación. Si hay trabajo activo que impide eliminarlo, la pantalla muestra el bloqueo.

El identificador está en **Identidad del perfil**. El proveedor y modelo siguen visibles para saber con qué configuración trabajas. La presencia de una herramienta en un perfil no demuestra que su servicio esté conectado ni que se haya ejecutado.

Para asignar modelos disponibles, abre Settings → proveedores → **Modelos activos**, habilita el uso que corresponda y guarda. Después elige proveedor y modelo al crear o editar el agente. La selección del modelo del orquestador en Chat es independiente de la asignación de un agente guardado.

## Proyectos, archivos y contexto

Abre **Workspace**. Sus pestañas son **Proyectos**, **Archivos** y **Contexto y memoria**. En Proyectos puedes crear o seleccionar el proyecto gestionado; la selección se conserva al cambiar de área. Si falta la carpeta de proyectos, el administrador debe configurarla antes de crear uno.

### Crear o abrir un proyecto

1. Escribe el nombre de carpeta y el título.
2. Pulsa **Revisar creación**.
3. Comprueba la ubicación completa y la operación. Abre **Detalles de la operación** si necesitas revisar sus datos.
4. Marca la confirmación y pulsa **Confirmar y ejecutar**.
5. Elige un proyecto ya existente en **Proyecto gestionado** para volver a abrirlo.

Un proyecto nuevo contiene sus documentos de contexto, estado y continuidad. Esos documentos son un punto de partida, no una acreditación de pruebas superadas. Sus estados iniciales pueden indicar `PREPARED` o `NOT_RUN`.

**Usar este proyecto en ADL** cambia la carpeta activa después de tu revisión. No concede automáticamente permisos de lectura al chat ni autoriza borrar archivos. La ubicación está disponible en **Ubicación del proyecto** y sigue visible al confirmar una operación.

### Archivos y papelera

En **Archivos → Explorador**, elige una carpeta y pulsa el archivo que quieras leer. Para crear uno, escribe su ruta relativa y contenido. Para editar, cambia el texto y pulsa **Revisar guardado**. La revisión de la copia leída se conserva en **Revisión del archivo**; evita sobrescribir silenciosamente un archivo que cambió después.

Para mover o renombrar, indica el destino relativo y pulsa **Revisar movimiento**. Para retirar un archivo, usa **Enviar a papelera**. Desde **Archivos → Papelera** puedes restaurarlo sin sobrescribir otro archivo o elegir **Eliminar definitivamente**. Esta última acción requiere revisión y no ofrece recuperación desde la papelera.

Si hay cambios sin guardar, guárdalos o descártalos antes de cambiar de archivo o proyecto. Los errores y conflictos se muestran sin presentar la operación como completada.

### Contexto y memoria

Abre la pestaña **Contexto y memoria** en Workspace para consultar la carpeta activa y los documentos del recorrido de lectura existente. **Examinar…** permite elegir carpeta; **Usar carpeta** aplica la selección y actualiza los datos que muestra esa pantalla.

Que un documento aparezca como no encontrado significa que no existe en esa ubicación reconocida; seleccionar una carpeta no inventa contexto o continuidad. Para consultar los documentos sembrados en la pantalla completa, primero usa el proyecto en ADL y abre **Contexto y memoria**. Una tarjeta de Workspace embebida muestra los documentos del proyecto seleccionado en esa misma pestaña. La memoria de conversación y una memoria general externa son conexiones diferentes: «Sin conectar» no se interpreta como una conexión activa.

## Git local y planes de GitHub

En un proyecto gestionado, abre **Archivos → Git y GitHub**.

1. Consulta el estado o inicializa un repositorio local nuevo después de revisar la operación.
2. Selecciona sólo los archivos que quieres incluir y abre el diff para revisar sus cambios.
3. Usa **Revisar preparación** y confirma la selección.
4. Escribe el mensaje y pulsa **Revisar commit**. Comprueba los archivos antes de confirmar.
5. Para crear una referencia de rama, indica el nombre y usa **Revisar rama**. Esta operación no cambia automáticamente la rama activa.

El servicio comprueba la revisión, el HEAD y la selección para evitar incluir preparación ajena. Un commit registra cambios locales; no equivale a aprobar el producto ni a publicar en GitHub.

**Planes GitHub** prepara información revisable para crear repositorios, PR, merges o revisar conflictos. En este recorrido son propuestas: no ejecutan operaciones remotas. Los conflictos necesitan texto de resolución explícito y revisión; no se aplica una elección automática de una versión completa.

## Contactos e importación de Google

### Agenda local

Abre **Contactos → Agenda**. La pestaña **Google** contiene la conexión e importación selectiva. Escribe nombre y al menos un teléfono o correo. Usa formato internacional para WhatsApp, con `+` y código de país. Guarda el contacto. Puedes buscarlo, editarlo y eliminarlo de la agenda local tras confirmar.

El contacto se guarda localmente. La eliminación local no borra contactos en Google ni mensajes enviados. Un contacto con correo pero sin teléfono sigue disponible en la agenda; no puede elegirse como destinatario de WhatsApp.

**Preparar mensaje** lleva el mismo contacto a Comunicaciones. También puedes abrir la pestaña **Contactos** dentro de Comunicaciones o **Herramientas → Contactos** dentro del Chat. Se utiliza la misma agenda; elegir un destinatario no envía un mensaje.

### Importar sólo algunos contactos de Google

Preparación del administrador: crear un cliente OAuth de escritorio, habilitar People API y guardar el archivo JSON fuera del repositorio. No pegues tokens ni el contenido del archivo en el chat.

1. Abre la pestaña **Google**, despliega **Configurar conexión con Google** e indica la ruta local de ese archivo.
2. Guarda la configuración y pulsa **Conectar con Google**.
3. Continúa en la ventana de Google y concede el permiso de lectura de contactos si estás de acuerdo.
4. Vuelve y pulsa **Comprobar conexión**.
5. Pulsa **Ver contactos para seleccionar**.
6. Filtra y marca las filas que quieres incorporar. No se eligen contactos automáticamente. Puedes seleccionar los visibles sin avisos o quitar la selección.
7. Revisa los avisos y duplicados, marca la confirmación y pulsa **Importar selección**.

Los duplicados se omiten sin sobrescribir. Una vista previa puede caducar; si ocurre, pide otra y revisa de nuevo la selección. «Autorización guardada» y «Lectura real comprobada» describen estados diferentes. Una vista previa de prueba aparece etiquetada y no demuestra conexión a tu cuenta.

## Vincular WhatsApp

1. Abre Settings → **WhatsApp**.
2. Escribe un nombre para la sesión, habilítala y guarda la configuración.
3. Pulsa **Abrir navegador y vincular QR**.
4. En tu teléfono, abre WhatsApp → dispositivos vinculados y escanea el QR de esa sesión.
5. Vuelve a BAGO y pulsa **Comprobar conexión**.

Es una sesión propia, conservada entre reinicios. Guardar una configuración no demuestra conexión; observa el estado y la fecha de comprobación. **Cerrar navegador conservando sesión** cierra la ventana utilizada por el puente y conserva la vinculación: no equivale a cerrar sesión en WhatsApp ni a desvincular el dispositivo.

No compartas QR, credenciales ni capturas con datos de otros contactos. Los envíos se revisan en Comunicaciones.

## Preparar mensajes y programarlos

En **Comunicaciones** tienes las pestañas **Mensaje**, **Historial** y **Contactos**. Los borradores se eligen junto al editor en Mensaje; el texto sin guardar se conserva al visitar otra pestaña. Puedes empezar en **Mensaje** o pedir al Chat que prepare un borrador. La tarjeta embebida y la pantalla completa editan el mismo borrador. **Abrir pantalla completa** conserva su identidad.

1. Elige el destinatario y comprueba su teléfono.
2. Escribe el mensaje.
3. Si adjuntas resultados, indica una ruta relativa exacta por línea dentro del workspace. Se admiten PDF, texto, CSV e imágenes, hasta cinco archivos de 10 MiB cada uno. La aceptación depende de la validación de ruta, tipo e integridad.
4. En **Cuándo**, elige ahora, una fecha concreta, cada día o cada semana. Revisa zona horaria, hora y días. Para una fecha concreta, incluye la zona u offset; por ejemplo `2026-10-30T10:00:00+01:00`.
5. Pulsa **Guardar y preparar revisión**.
6. Comprueba el destinatario, texto, adjuntos, calendario y próxima ejecución de la copia guardada. Las huellas de adjuntos están desplegadas bajo demanda.
7. Marca la confirmación y pulsa **Confirmar y enviar ahora** o **Confirmar programación**.

Cambiar el borrador exige guardarlo y revisar otra vez. Si otra sesión lo cambió, tu texto se conserva y puedes cargar la versión actual o preparar tus cambios sobre ella.

La pestaña **Historial** conserva los resultados y sus recibos. Si una operación queda como incierta, no se reintenta automáticamente: comprueba si llegó antes de preparar otra. Cancelar futuras ejecuciones no retira un mensaje que ya se haya enviado.

## Experimento de lectura y revisión

Este recorrido sirve para estudiar una empresa o página pública con un agente y preparar un resultado verificable.

1. Define antes qué quieres comprobar, qué páginas están autorizadas y qué resultado esperas. Por ejemplo: identificar servicios publicados y distinguirlos de una interpretación del agente.
2. Crea o selecciona el agente y comprueba el modelo asignado. Usa una conversación nueva para mantener claro el alcance.
3. Autoriza la lectura web por turno y envía la tarea desde Chat.
4. Espera el resultado real. Una respuesta del modelo sin una fuente leída correctamente no acredita el análisis de la página.
5. Abre Fuentes web y contrasta afirmaciones con el texto capturado. Revisa URLs, UTC y hashes; después abre la ejecución de esa misma respuesta.
6. Si se usa Jaeger, comprueba que la traza exportada se recupera por su identificador. Una confirmación del exportador por sí sola no demuestra esa consulta.
7. Registra qué pasó, qué falló y qué no se ejecutó. Toma capturas actuales durante el recorrido; oculta datos personales en las copias que vayas a compartir.
8. Prepara un informe o PDF y comprueba contenido, apertura y adjuntos. Esta interfaz no convierte automáticamente cualquier respuesta en un informe validado.
9. Si la entrega al cliente está autorizada y los criterios exigidos pasan, prepara el mensaje en Comunicaciones. Revisa de nuevo contacto, archivos y calendario antes del envío final.

Esta guía describe el recorrido; no afirma que un experimento concreto haya pasado. Sus resultados deben consultarse en el registro de esa ejecución.

## Si algo no funciona

| Lo que ves | Qué hacer |
| --- | --- |
| No hay modelos disponibles | Revisar proveedor y Modelos activos en Settings. No basta con tener un nombre de modelo guardado. |
| La lectura web es denegada | Revisar HTTPS, origen autorizado, conversación y turno. Volver a autorizar expresamente un turno nuevo si corresponde. |
| La página devuelve poco texto | Puede depender de JavaScript, autenticación o un tipo no admitido. No dar por leído contenido ausente. |
| Falta una fuente o traza | Mantener «no disponible» y consultar la ejecución correcta. No sustituirla por la demo histórica. |
| No aparecen documentos de contexto | Revisar la carpeta activa y si existen los archivos reconocidos. |
| Un guardado o importación detecta conflicto | Cargar la revisión actual y volver a revisar los cambios. |
| Google no está conectado | Configurar el cliente, completar el consentimiento y comprobar el estado. |
| WhatsApp no aparece conectado | Abrir su navegador, comprobar la vinculación y volver a consultar el estado. |
| Envío incierto | Comprobar recepción antes de reintentar; evitar duplicados. |

## Información para administración e integración

La carpeta de proyectos gestionados se configura mediante `BAGO_WORKSPACE_PARENT`, con una carpeta dedicada existente. Los documentos sembrados son `.bago/context/PROJECT_CONTEXT.md`, `.bago/state/PROJECT_STATE.json` y `.bago/runtime/ACTIVE_HANDOFF.md`. El recorrido de selección de una carpeta existente no concede permisos de modificación.

Contactos, operaciones de workspace y lectura web tienen núcleos independientes de BAGO. El adaptador ADL consume esas capacidades; no debe ser el único modo de usarlas. Las instrucciones de sus paquetes incluyen CLI, SDK, contratos, procedencia y pruebas aisladas. La disponibilidad de un servidor externo, una cuenta o una autorización personal se verifica aparte.

El lector web estándar acepta HTML, XHTML o texto. No carga subrecursos, cookies, proxies de sistema ni scripts. Valida cada destino y redirección, liga la conexión al IP validado y comprueba TLS por el hostname. Sus límites incluyen ocho intentos de herramienta por turno, tres redirecciones por página, 1 MiB por cuerpo y texto acotado a 24.000 caracteres. La espera DNS está acotada; el resolvedor del sistema en curso no puede detenerse a la fuerza. Esto no establece un sandbox global para otros procesos del host.

Las capturas conservan bytes originales, texto y manifiesto. Se revalidan antes de devolver una fuente exitosa. Una escritura parcial o un fallo de persistencia es un fallo, no una lectura correcta. Los grants del Chat están en memoria, caducan y no sobreviven a un reinicio; deben solicitarse de nuevo. Los detalles y comandos completos de lectura independiente están en `src/web_research/README.md` del paquete.

No registres tokens, QR, contenido privado o números de clientes en documentación pública. Conserva informes y evidencias ligados a la candidata y al entorno que realmente los produjeron.
