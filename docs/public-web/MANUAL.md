# Manual de uso de BAGO ADL

Guía para trabajar desde el chat y las pantallas de BAGO. Abre una sección según lo que necesites hacer. Las explicaciones y detalles técnicos están aquí para que las pantallas puedan mostrar primero tu tarea.

## Contenido

- [Orientarse y empezar](#orientarse-y-empezar)
- [Barra de estado](#barra-de-estado)
- [Chat y lectura de páginas públicas](#chat-y-lectura-de-páginas-públicas)
- [Historial de trabajos](#historial-de-trabajos)
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

La barra lateral permite cambiar entre Workspace, el grupo **BAGO5**, Agentes y Comunicaciones. **BAGO5** contiene **Chat**, el orquestador general con historial de conversaciones, y **Capacidades**; Agentes contiene Mis agentes, Crear agente, Ejecutar / Probar y Evaluación. Las conexiones externas se gestionan desde **Configuración → Conexiones externas**; las herramientas asignadas a cada perfil se revisan al editar ese agente. El panel **BAGO5 · Conversaciones y agentes** muestra los perfiles que realmente se usaron en la conversación abierta, no el catálogo general. Inspector abre la revisión de una ejecución. Manual abre esta guía en otra pestaña.

**Capacidades** presenta una lista agrupada en Documentos, Archivos y espacio de trabajo, Agentes y evaluación, Desarrollo de BAGO ADL, Revisión y entrega, y Conexiones y ejecución. El menú plegable **Opciones rápidas**, fijo al pie de esta pantalla, permite saltar a cada grupo. Las etiquetas de color resumen efecto, proveedor e integración; el estado disponible no concede permisos. Cada capacidad conserva su explicación, requisitos, acción y detalles técnicos. Las acciones que preparan un mensaje lo añaden al borrador de BAGO5 para que lo revises; no lo envían automáticamente. Ver una capacidad o guardar una propuesta tampoco la asigna por sí solo a un agente.

En **Configuración → Conexiones externas** puedes guardar una conexión y descubrir las herramientas que ofrece. Esas herramientas aparecen en la ficha de la conexión; descubrirlas no las ejecuta ni las asigna a agentes. **Agentes → Mis agentes → Editar** muestra tipo, proveedor y modelo, alcance de asignación y herramientas configuradas para ese perfil. El menú **Recursos** del compositor sirve para abrir recursos contextuales del chat y no sustituye a esos destinos.

![Lista de capacidades agrupada y menú de opciones rápidas en BAGO5](images/capabilities-list-quick-menu.png)

**Los bloques con flecha se pueden desplegar.** Pulsa su cabecera para ver más información y vuelve a pulsarla para recogerla. También puedes llegar con la tecla Tab y abrirlos con Enter o Espacio. El contorno resalta el control seleccionado con el teclado.

Las pestañas superiores separan las áreas de una pantalla. Puedes pulsarlas o usar Tab y las flechas izquierda/derecha; Inicio y Fin llevan a la primera y última. Cambiar de pestaña conserva lo que estabas editando.

Los cambios que necesitan revisión muestran primero una propuesta o un borrador. Lee los datos, marca la confirmación y pulsa la acción final cuando estés de acuerdo. Un borrador guardado no significa que se haya enviado un mensaje ni ejecutado una operación. Las tareas conversacionales dentro del alcance pueden enviarse sin una tarjeta repetida por delegación; el host comprueba el alcance antes del turno hijo. Si el agente necesita herramientas conectadas, BAGO5 presenta una tarjeta para revisar las herramientas asignadas y autorizar el efecto y la carpeta exacta. La asignación de una herramienta no concede ese permiso.

## Barra de estado

Al pie de BAGO5 aparece una barra con cinco grupos. Pulsa uno para abrir sus detalles; **Cerrar detalles** o Escape lo recoge y devuelve el foco al mismo control. El panel separa el resumen observado, las tarjetas de datos y la fecha/vigencia. Las tarjetas se reparten en dos columnas en escritorio y una en móvil, con desplazamiento interno si falta espacio. Cada sección tiene un acento de color; la etiqueta de estado conserva un color independiente y su texto, por ejemplo un proveedor configurado sigue sin respuesta verificada. La barra ocupa su propia fila y no tapa el cuadro de escritura.

- **Memoria** distingue el historial de conversación de la memoria general. Que el historial esté disponible sólo acredita metadatos: no demuestra que haya mensajes ni que se hayan recuperado correctamente. **General sin conectar** conserva su significado independiente.
- **Backend** indica que la API respondió a la consulta de estado; no certifica el funcionamiento de todo el sistema.
- **Actividad ADL** cuenta las solicitudes HTTP activas en el proceso actual de la API. Cero es un valor observado, distinto de **Sin comprobar**. El contador no representa tareas terminadas, agentes, trabajos de fondo ni la actividad de Codex.
- **Git** muestra el repositorio local, la rama y si hay un remoto configurado, cuando pueden consultarse. Un remoto configurado no demuestra conexión ni autenticación con GitHub. Un dato no disponible no se sustituye por «sin repositorio».
- **Proveedores** muestra los metadatos guardados del proveedor y modelo. **Configurado** o **registrado** no significa que haya conexión actual ni una respuesta verificada. La barra no envía mensajes de prueba al modelo.

La consulta de metadatos se repite cada 30 segundos con la pestaña visible. Se pausa al ocultarla y se vuelve a consultar al regresar. **Actualizar** permite solicitar otra lectura; no cambia la carpeta, el proveedor, los permisos ni ejecuta tareas. Los detalles muestran la fecha de observación en UTC. Git puede conservar durante unos segundos una observación en caché con su fecha original.

Si la consulta falla, se muestra el aviso y se conservan los valores anteriores con la etiqueta **Anterior**; no se presentan como una comprobación nueva. Una observación de más de un minuto también se marca como anterior. **Sin comprobar** indica que falta una lectura válida, no un fallo demostrado de ese servicio.

## Chat y lectura de páginas públicas

Si el agente devuelve una tarea por estar fuera de su alcance, BAGO5 registra la devolución, excluye a ese agente y busca otro perfil; no vuelve a asignársela en ese recorrido. Si ninguno encaja con una tarea clara, puede crear un perfil limitado a esa tarea y seleccionar las herramientas necesarias entre las que están conectadas al chat de agentes. Las herramientas no conectadas —incluido MCP genérico— no se asignan como si estuvieran disponibles. Si el perfil nuevo necesita herramientas, queda como propuesta y no inicia el turno hijo hasta que confirmes los permisos y la carpeta; si no necesita herramientas, puede ejecutar el turno conversacional tras comprobar el alcance. El alcance de tareas no concede permisos de lectura del Workspace, documentos, herramientas, desarrollo, exportación, escritura de archivos ni comunicaciones. Esas acciones conservan su autorización específica. Una devolución o una necesidad de permiso no se presenta como tarea completada.

**MCP y servicios externos:** en **Configuración → Conexiones externas** puedes configurar Docker MCP, MCP HTTP o una API HTTP, descubrir herramientas y, desde esa pantalla, invocarlas con una confirmación explícita y argumentos revisados. El recibo y la traza de esa llamada pertenecen a la conexión. Actualmente, descubrir herramientas no las incorpora a **Agentes → Editar → Herramientas** ni habilita ejecución MCP desde el chat de un agente; esa integración sigue pendiente. BAGO5 no asigna credenciales ni efectos externos al crear o elegir un agente.

1. Abre **BAGO5 > Chat**. El interlocutor general es **Orquestador BAGO5** y conserva un historial de conversaciones; puedes abrir manualmente una conversación anterior desde el panel de contexto. La bandeja **BAGO5 · Conversaciones y agentes** muestra los agentes utilizados en la conversación abierta.
2. Explica tu intención al **Orquestador BAGO5**. Define en cada perfil el campo **Tareas que BAGO5 puede asignar automáticamente a este agente**. BAGO5 compara la tarea con esos alcances. Si ninguno encaja con una tarea clara, crea un perfil limitado al encargo y selecciona solo herramientas necesarias conectadas al chat. Un turno conversacional sin herramientas puede enviarse sin tarjeta repetida tras validar el alcance. Cuando la tarea necesita herramientas, revisa la tarjeta de delegación, elige la carpeta exacta y autoriza explícitamente los efectos antes de ejecutar; asignar herramientas al perfil no autoriza su uso.
3. Elige el modelo disponible para ese interlocutor. Si no hay ninguno, configura el proveedor en Settings.
4. Escribe lo que quieres obtener, con una tarea concreta. Por ejemplo: «Resume los servicios descritos en esta página y cita las fuentes que hayas leído».
5. Si necesitas consultar la web, marca **Permitir lectura web pública**.
6. Pega una o varias URL HTTPS en **URL HTTPS de entrada · una por línea**. Se admiten hasta ocho entradas distintas. Revisa los orígenes que aparecen debajo.
7. Pulsa **Send**. El permiso vale para ese turno, esa conversación y ese interlocutor. La casilla vuelve a quedar desmarcada.

Al desplazarte por una conversación larga aparecen unos segundos los botones **Ir al principio de la conversación** y **Ir al final de la conversación**.

Los atajos del chat se reconocen cuando el mensaje completo pide una sola acción, por ejemplo **«Lista mis agentes»**, **«Lista capacidades»** o **«Proponer capacidad workspace.read_text»**. Una tarea que menciona agentes, capacidades, «hay» o «tengo» dentro de una explicación conserva el recorrido normal del chat; esas palabras no sustituyen tu encargo por un listado. Los atajos tampoco conceden permisos ni ejecutan herramientas. Las sugerencias sólo rellenan el borrador hasta que pulses **Enviar**.

Ejemplo de entrada pública: `https://www.sollutia.com/es/empresa.html`. La disponibilidad de la página depende de su servidor.

El permiso permite leer páginas de los orígenes indicados. Una URL de entrada no autoriza por sí sola otros dominios a los que enlace. El lector rechaza credenciales, destinos locales o privados y redirecciones fuera del alcance autorizado. No ejecuta los scripts de las páginas ni inicia sesión en ellas. Una página que necesita JavaScript o acceso privado puede no aportar el contenido que buscas.

**Lectura local:** la casilla **Allow project file reads** es un permiso independiente. Si la necesitas, indica las rutas relativas exactas de los archivos del proyecto. Marcar lectura web no concede lectura de archivos; ambos permisos pueden utilizarse expresamente en el mismo turno.

El texto de una página puede contener instrucciones ajenas a tu tarea. Se trata como fuente externa, no como una orden tuya. Comprueba las afirmaciones antes de usarlas como resultado para un cliente.

## Historial de trabajos

La vista **Historial de trabajos**, también cuando aparece dentro del chat, reúne metadatos de cinco fuentes: trabajos legacy, ejecuciones de tarea, delegaciones, turnos de agente y evaluaciones. Elige una fuente para filtrar en el servidor; **Anterior**, **Siguiente** y **Primera página** recorren los registros enumerados. **Actualizar** solicita de nuevo la página actual. La vista no se recarga cada cinco segundos.

Cada fila conserva la fuente, el estado exacto, el agente histórico cuando consta y su última actividad con fecha y hora UTC. **Respuesta recibida (PASSED o answered)** significa que se recibió una respuesta; no acredita que el encargo esté terminado ni que se hayan ejecutado herramientas. Los intentos fallidos y los registros relacionados se conservan por separado.

Selecciona una fila para consultar identificadores, referencia de traza y recibo, fechas, duración, coste y efectos registrados. No se abren cuerpos de conversaciones ni documentos, y seleccionar no ejecuta ni repite trabajos. Un ID de traza o recibo es una referencia registrada, no una verificación nueva. **No registrado** se distingue de cero y de **No** en herramientas o escritura.

La sección **Fuentes del historial** indica si cada fuente está disponible, ausente, parcial o no disponible. Si la cobertura es incompleta, el total sólo corresponde a los registros enumerados. Un error de conexión o formato se muestra como error; si se conservan datos anteriores, se avisa de que no se han actualizado. Puedes volver a intentarlo con **Actualizar**.

## Revisar fuentes y ejecuciones

Después de una respuesta, despliega **Fuentes web** o **Archivos consultados** para ver las referencias conservadas. Durante el desplazamiento por una conversación larga aparecen brevemente botones para saltar al principio o al final.

Una respuesta sin fuentes registradas no demuestra que se haya leído una página o un archivo.

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

Las fichas de agentes se muestran en una lista. Cada una separa el tipo, proveedor y modelo, alcance para asignación automática y herramientas configuradas; **Identidad del perfil** contiene el identificador. Si falta el alcance, BAGO5 no asignará tareas automáticamente a ese perfil. La presencia de una herramienta en un perfil no demuestra que su servicio esté conectado ni que se haya ejecutado.

Para asignar modelos disponibles, abre Settings → proveedores → **Modelos activos**, habilita el uso que corresponda y guarda. Después elige proveedor y modelo al crear o editar el agente. La selección del modelo del orquestador en Chat es independiente de la asignación de un agente guardado.

## Proyectos, archivos y contexto

Abre **Workspace**. Sus pestañas son **Proyectos**, **Archivos** y **Contexto y memoria**. **Proyectos** reúne la carpeta, el nombre y el título. La carpeta activa es global para ADL; no representa un aislamiento por conversación.

### Elegir la carpeta de un proyecto

1. La opción inicial **Usar esta carpeta existente** toma exactamente la carpeta activa. Puedes escribir otra ruta absoluta o pulsar **Examinar…**. Examinar sólo devuelve una selección; no cambia la carpeta activa ni crea archivos.
2. Si quieres una subcarpeta nueva, elige explícitamente **Crear una carpeta hija**, selecciona su padre y escribe el nombre de carpeta y el título. En el modo existente no se renombra la carpeta elegida. Los metadatos de un proyecto ya registrado se conservan; la revisión muestra su nombre y título reales.
3. Pulsa **Usar carpeta** para preparar el plan calculado por el servicio. Revisa **Destino exacto**, la carpeta activa esperada y la caducidad. Cada archivo indica el estado observado: **Falta · se creará** o **Existe · se conserva**. Los directorios técnicos están plegados y puedes desplegar su lista completa. Preparar el plan todavía no escribe ni cambia la selección; si las condiciones cambian después, el servicio rechaza el plan obsoleto.
4. Marca la confirmación y pulsa **Confirmar y ejecutar**. La confirmación se refiere únicamente al identificador y hash de ese plan. Cambiar ruta, modo, nombre o título invalida el plan y el consentimiento, incluso si restauras después el valor anterior. **Cancelar** conserva tus borradores.
5. Sólo después de la confirmación el servicio inicializa los mínimos ausentes y selecciona el destino. Conserva los archivos presentes sin sobrescribirlos; no crea el formato experimental `.b5ws`. Los documentos de contexto, estado y continuidad son un punto de partida, no una acreditación de pruebas superadas.

**Proyecto gestionado** reúne proyectos registrados por la selección exacta y proyectos del servicio anterior. Abrir uno permite usar sus controles de archivos; **Usar este proyecto en ADL** prepara igualmente un plan para su raíz exacta. No concede permisos de lectura al chat ni a herramientas. No se sustituye tu carpeta elegida por una carpeta administrativa alternativa.

Los errores, planes caducados y conflictos no se presentan como selección completada. Si hubo un fallo parcial, consulta el **Recibo devuelto por el servicio**: la lista de archivos/directorios creados y el estado de selección son los observados por el backend. No se reintenta automáticamente ni se ejecuta de nuevo un plan antiguo.

### Archivos y papelera

En **Archivos → Explorador**, elige una carpeta y pulsa el archivo que quieras leer. Para crear uno, escribe su ruta relativa y contenido. Para editar, cambia el texto y pulsa **Revisar guardado**. La revisión de la copia leída se conserva en **Revisión del archivo**; evita sobrescribir silenciosamente un archivo que cambió después.

Para mover o renombrar, indica el destino relativo y pulsa **Revisar movimiento**. Para retirar un archivo, usa **Enviar a papelera**. Desde **Archivos → Papelera** puedes restaurarlo sin sobrescribir otro archivo o elegir **Eliminar definitivamente**. Esta última acción requiere revisión y no ofrece recuperación desde la papelera.

Si hay cambios sin guardar, guárdalos o descártalos antes de cambiar de archivo o proyecto. Los errores y conflictos se muestran sin presentar la operación como completada.

### Contexto y memoria

Abre **Contexto y memoria** para ver la misma carpeta activa y los documentos de lectura existentes. **Editar carpeta en Proyectos** vuelve al formulario de selección; esta vista de Contexto no cambia la carpeta ni abre el selector por su cuenta.

Que un documento aparezca como no encontrado significa que no existe en esa ubicación reconocida. El plan confirmado en Proyectos puede crear únicamente los mínimos ausentes; seleccionar o abrir el panel no inventa contexto ni continuidad. La memoria de conversación y una memoria general externa son conexiones diferentes: «Sin conectar» no se interpreta como una conexión activa.

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

1. Abre **Contactos → Google** y selecciona el archivo JSON OAuth. BAGO valida y guarda localmente los datos necesarios; no conserva el archivo completo.
2. Pulsa **Conectar con Google** y concede el permiso de solo lectura si estás de acuerdo. Elegir el archivo por sí solo no conecta la cuenta.
3. Vuelve y pulsa **Comprobar conexión**.
4. Pulsa **Ver contactos para seleccionar**.
5. Filtra y marca las filas que quieres incorporar. No se eligen contactos automáticamente. Puedes seleccionar los visibles sin avisos o quitar la selección.
6. Revisa los avisos y duplicados, marca la confirmación y pulsa **Importar selección**.

Si no puedes usar el selector, abre **Configuración avanzada: escribir una ruta** e indica la ruta local del mismo archivo.

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

**Limitación observada el 25/10/2026:** el transporte de BAGO puede terminar como incierto mientras el mensaje sigue sin enviar en el editor de WhatsApp. El estado incierto no demuestra ni envío ni recepción. Comprueba la conversación y el mensaje saliente exactos antes de actuar; no confirmes otra operación para repetirlo. Si una persona autorizada completa el envío directamente en WhatsApp, esa acción y su comprobación se registran por separado: el recibo incierto original de BAGO se conserva y no se presenta como un envío automático verificado.

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
