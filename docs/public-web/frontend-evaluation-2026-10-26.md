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
