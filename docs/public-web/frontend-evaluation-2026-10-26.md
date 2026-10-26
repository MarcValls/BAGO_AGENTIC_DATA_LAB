# Evaluación del frontend ADL — 26-10-2026

**Alcance observado:** navegador local `http://127.0.0.1:8093/`, backend `8098`, candidato comunicado por `/api/integration-preview-identity`: `orchestrator-delegation-r42-preview`, PID 27708, iniciado el 25-10-2026 23:07 +01:00. La identidad pertenece a un preview local externo; esta evaluación no certifica `main` ni la versión publicada. Revisión visual y lectura de interfaz/contratos, sin modificar datos ni lanzar tareas.

## Hallazgos prioritarios

| Prioridad | Hallazgo observado | Efecto para la persona | Siguiente ajuste recomendado |
|---|---|---|---|
| P1 | **Workspace y conversaciones no quedan aislados por proyecto.** Workspace informa que la carpeta activa es global para ADL; `WorkspaceManager` consume `scope: global_workspace` (`frontend/src/components/WorkspaceManager.tsx:45-89`). | Se puede cambiar de carpeta sin que cada proyecto tenga su propio contexto y sus chats. Contradice el uso solicitado de chats separados por proyecto. | Incorporar un vínculo de proyecto explícito en conversación y grants; seleccionar la carpeta desde el alta/selección del proyecto. Migración y compatibilidad del historial deben definirse antes de cambiar datos. |
| P1 | **El selector del Chat mezcla modelos registrados y estados sin verificar.** La interfaz actual muestra una lista larga de Ollama, OpenAI Codex y GitHub Copilot; la mayoría aparece «sin verificar». El modelo elegido no queda limitado de forma visible al catálogo de modelos activos. El código obtiene `/api/providers/chat-models` (`AgentChat.tsx:378`); Settings ya distingue pestañas de proveedores y modelos activos (`ProviderSettings.tsx:139-143`). | Cuesta saber qué modelos están listos y la pantalla de chat duplica una decisión que el usuario indicó que quiere tomar en Modelos activos. | Poblar el selector solo con modelos activados y recientemente verificados; mantener la habilitación y deshabilitación exclusivamente en la pantalla Modelos activos. Mostrar errores/antigüedad del chequeo junto al proveedor. |
| P1 | **Historial de trabajos está vacío en el preview.** `GET /api/jobs/list` respondió HTTP 200 con `{"jobs":[]}` durante esta revisión. | La pantalla existe, pero no ayuda a inspeccionar trabajo previo cuando el registro consultado no contiene ejecuciones. | Aclarar qué registro alimenta la vista; correlacionar taskruns/delegaciones con conversación e Inspector o mostrar una explicación explícita de alcance cuando está vacío. |
| P1 | **El estado del pie informa Git y proveedor como no disponibles/sin respuesta verificada.** La barra muestra «Git no disponible» y proveedor registrado sin respuesta verificada; el estado del backend sí indica API responde. | El usuario no sabe si debe esperar, configurar credenciales o si la función no está conectada. El texto de proveedor queda truncado en el ancho actual. | Añadir detalle desplegable por estado, acción contextual para conectar/comprobar y texto completo accesible por foco/tooltip; separar «no configurado», «sin verificar», «error» y «listo». |
| P2 | **Herramientas no tiene destino lateral propio.** La navegación observada bajo Agentes muestra Mis agentes, Crear agente, Ejecutar / Probar y Evaluación. El catálogo Capacidades está en el grupo BAGO5; el formulario del agente contiene la configuración de herramientas (`agents.AgentBuilder.available_tools`). | Para una persona nueva no es obvio dónde encontrar conexiones externas frente a capacidades del Chat y herramientas asignables a perfiles. | Mantener la distinción que pidió el usuario: Herramientas como submenú de Agentes y Capacidades como submenú de Chat, evitando que el catálogo parezca una asignación automática. |
| P2 | **Densidad y tipografía.** La barra lateral, mensajes de ayuda y el pie usan texto pequeño; varios estados se truncan en el layout de escritorio observado. | Cuesta leer mensajes largos y comparar estados rápidamente, especialmente en las tarjetas y la barra inferior. | Subir tamaño/peso de texto secundario, distribuir los estados del pie en un panel expandible y revisar contraste/foco a 100% y 125% de escala. |

## Lo que ya está bien encaminado

- Chat general aparece como **Orquestador BAGO5**, con permiso de lectura de archivos desmarcado y alcance explicado en el panel de Workspace.
- El catálogo de capacidades distingue efecto, proveedor e integración y advierte que disponibilidad no concede permiso ni demuestra ejecución.
- El formulario de agente explica que su alcance conversacional no autoriza automáticamente workspace ni efectos en archivos.
- Settings separa Proveedores de Modelos activos, aunque la elección desde el Chat todavía no refleja claramente ese límite.
- Inspector separa conversación actual y demostración histórica; no deben confundirse.

## Mapa de navegación observado

- **BAGO5:** Chat del orquestador; Capacidades.
- **Agentes:** Mis agentes; Crear agente; Ejecutar / Probar; Evaluación.
- **Comunicaciones:** Mensajes; Historial; Contactos.
- **Workspace:** Proyectos; Archivos; Contexto y memoria.
- **Inspector:** revisión de decisiones, ejecución, trazas y registros relacionados.
- **Configuración:** Cognición y contexto; Proveedores y modelos; Conexiones externas; WhatsApp.

## Recomendación de cierre de interfaz

Para considerar completo el frontend, los siguientes hitos deben ser verificables en el runtime: (1) contexto y conversaciones aislados por proyecto, (2) selección de modelos alineada con Modelos activos y respuesta de proveedor comprobada, (3) historial que consulte ejecuciones reales o explique su alcance vacío, (4) navegación explícita Herramientas/Capacidades según la decisión del usuario y (5) legibilidad del pie y los estados de error. Las capturas del manual son orientación visual; no sustituyen pruebas de estas funciones.

**Estado:** revisión `VERIFIED` para lo observado en el preview local indicado; aceptación del frontend completo `NOT_VALIDATED`. No se hicieron cambios de código en la aplicación ni pruebas automatizadas de UI.

## Revisión de continuidad - 26-10-2026

Se repitió la inspección del escritorio de `http://127.0.0.1:8093/` y las consultas de sólo lectura al backend `8098`. El preview sigue identificado como `orchestrator-delegation-r42-preview` (PID 27708); no corresponde al candidato de código `project-workspace-chat-isolation-20261026`.

### Verificación del estado visible

- La API de salud responde HTTP 200. La ruta nueva `/api/project-folders/v1/active` responde HTTP 404, así que el runtime no tiene cargada la identificación de proyecto incorporada en el candidato.
- El workspace informado por el preview sigue con alcance `global_workspace`. El historial del Chat contiene conversaciones de distintos trabajos sin una etiqueta de proyecto; esta captura no demuestra aislamiento por proyecto.
- `/api/jobs/list` sigue respondiendo HTTP 200 con `jobs: []`.
- La pantalla muestra un selector largo de modelos con muchos rótulos `sin verificar`. La comprobación de `/api/providers/chat-models` no terminó dentro del timeout de 5 segundos; no se interpreta ese timeout como prueba de que todos los modelos fallen.
- La barra inferior presenta texto recortado en estados de Memoria y Proveedores, y `Git no disponible`. El snapshot visible conserva una tipografía secundaria pequeña en el chat, el historial y el pie.
- La navegación observada sigue mostrando `Capacidades` bajo BAGO5 y no muestra un destino `Herramientas` bajo Agentes. El usuario había pedido distinguir esos dos destinos.

La captura local de esta observación se conservó fuera del repositorio en `C:\BAGO_TESTS\BAGO5_ADL\frontend-evaluation-20261026\current-8093-preview.png`; contiene títulos de conversaciones y no se publica en esta rama documental.

### Cambio de código preparado en rama separada

En la rama de trabajo `fix/project-workspace-chat-isolation-20261026` se preparó aislamiento de historial por identidad estable para proyectos registrados; las carpetas que todavía no están registradas permanecen en el ámbito general y conservan el historial legado. La UI del Chat muestra el nombre del proyecto activo o indica que el workspace aún no está registrado. El alcance cubre biblioteca, Chat BAGO5, chat REST de agente, Inspección, historial, propuestas ligadas a conversaciones y el WebSocket legado de chat. Verificaciones focalizadas: 88 pruebas Python de conversaciones/proyectos/rutas y 10 pruebas Vitest de arranque pasaron; `npm run build` pasó con aviso de bundle principal mayor a 500 kB. Estos resultados no pertenecen al preview 8093.

La suite frontend completa del candidato registró 24 fallos y 766 pruebas aprobadas (790 en total). Se comprobó que dos de esos fallos ya se reproducen en la base exacta `52432e5adf0be349eeb24c06bbbaf1acbb4a3f7c`; los otros 22 aún requieren clasificación diferencial. La suite Python completa se ejecutó con un `LOCALAPPDATA` de prueba aislado: 1570 aprobadas, 2 saltadas y 22 subpruebas. `generate_dynamic_readme.py` generó README después de las 1570 pruebas aprobadas y `--check --skip-tests` verificó el archivo (1572 casos recogidos). La primera ejecución sin aislamiento falló por heredar el workspace real del perfil; no se usa como evidencia de la ejecución final.

**Estado de esta revisión:** observaciones del runtime `VERIFIED`; código de aislamiento por proyecto en `4946a8f` `EXECUTED` y verificado por la suite Python completa (1570 aprobadas, 2 saltadas), pruebas focalizadas de UI y build; despliegue en 8093 y validación visual del candidato `NOT_RUN`. El frontend completo sigue `NOT_VALIDATED` por los 24 fallos de Vitest y los hallazgos de interfaz pendientes.

## Revisión visual y funcional de escritorio - 26-10-2026 01:03 UTC

Se volvió a observar la pestaña existente de Brave `http://127.0.0.1:8093/`, sin navegar, hacer clic ni enviar mensajes. El backend `8098` responde `200`; `/api/integration-preview-identity` conserva `orchestrator-delegation-r42-preview`, PID `27708`, y workspace `C:\BAGO_TESTS\DUAL_MISSIONS_20261024\tools-runtime-01\workspace`. El preview sigue siendo distinto del candidato de código `4946a8f` y no se considera despliegue del candidato.

### Comprobaciones directas

- La vista del Chat general carga en blanco, con la barra lateral y el panel derecho Proyecto/Historial visibles; la captura no muestra una superposición de error de Vite. El log de consola del navegador y las interacciones no se inspeccionaron.
- La navegación muestra `Capacidades` bajo BAGO5. Bajo Agentes siguen sin aparecer `Herramientas`; aparecen Mis agentes, Crear agente, Ejecutar / Probar y Evaluación.
- El DOM expone varios modelos con estado visible `sin verificar`. `/api/providers/selection` devuelve `codex/gpt-6-luna` con estado `ready`, mientras `/api/runtime/status` describe el proveedor como metadata de registro y `response_verified:false`. `/api/providers/chat-models` superó el timeout de lectura de 5 segundos; ese timeout no demuestra que todos los modelos fallen ni justifica seleccionar o desactivar modelos.
- `/api/project-folders/v1/active` devuelve `404`; el panel de Workspace explica permisos del siguiente envío, pero este preview no prueba la asociación de una carpeta y conversaciones por proyecto. La ruta nueva sí está en el candidato separado, aún no en este runtime.
- Hay dos registros de historial distintos: `/api/jobs/list` sigue devolviendo `jobs:[]`, pero `GET /api/work-history` devuelve 50 elementos (36 `agent_turn` completos, 8 fallidos, 3 delegaciones y 3 `task_run`). Por tanto, no es correcto decir que todo el historial de trabajo está vacío. La vista observada en el panel derecho es Historial de conversaciones; el historial agregado de trabajos es otra pantalla, global y sin navegación de vuelta al chat. Su contrato actual tampoco recopila turnos directos del orquestador BAGO5 como `agent_turn`.
- En la captura de escritorio, los textos largos de Memoria y Proveedores terminan recortados con puntos suspensivos. Los datos del pie sí distinguen historial de conversación disponible, memoria general desconectada, API respondiendo, actividad de solicitudes del proceso en reposo, Git no disponible y proveedor sin respuesta verificada.

### Dictamen actualizado

La pantalla inicial de escritorio está renderizada y las decisiones de layout ya visibles (logo en la barra izquierda, Chat general en blanco y panel derecho recuperado) se conservan en este preview. Para completar el frontend aún hacen falta: (1) activar en el runtime el aislamiento de workspace/conversaciones por proyecto, (2) reflejar con claridad el inventario de modelos activos y las verificaciones reales del proveedor, (3) enlazar el historial de trabajos con los turnos y conversaciones del orquestador BAGO5, (4) añadir el destino Herramientas bajo Agentes respetando que las conexiones permanecen en Configuración, y (5) evitar el truncado del pie en anchos de escritorio menores.

**Estado:** identidad, respuestas HTTP y contenido visual de esta vista `VERIFIED` sólo para el preview indicado; comprobaciones de consola e interacción `NOT_RUN`; frontend completo `NOT_VALIDATED`. La pantalla/captura no certifica ejecución de herramientas, aislamiento del candidato, salud de todos los proveedores ni trazas completas.
