# Evaluación del frontend - 26 de octubre de 2026

## Alcance observado

Revisión estática del frontend y revisión visual de escritorio a 1920 × 1080 en `http://127.0.0.1:8093`. La página respondió HTTP 200 y no produjo excepciones JavaScript durante la carga inicial. El backend de 8093 y 8098 se identifica como `orchestrator-delegation-r42-preview`; por tanto, esta observación no acredita que el runtime ejecute la rama de la PR #71. No se pudo abrir una ventana UI dedicada mediante el conector de navegador. La revisión visual se hizo con Playwright headless.

La captura se conserva fuera del repositorio porque contiene datos de conversaciones del runtime local:

`C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\adl-frontend-review-20261026\runtime-8093-desktop.png`

## Lo que ya está presente en el código y la vista

- Chat principal de BAGO5, historial de conversaciones y selección explícita de conversación.
- Panel derecho de carpeta de trabajo e historial de conversaciones en la vista observada.
- Barra inferior con indicadores de memoria, backend, actividad HTTP, Git y proveedor.
- Historial de trabajo unificado con fuentes legacy, task runs, delegaciones, turnos de agente y evaluaciones; enumera cobertura parcial y separa estado observado de finalización.
- Catálogo de capacidades separado de agentes y acciones para navegar a configuración de conexiones.
- El panel de actividad limita correctamente su afirmación a solicitudes HTTP del proceso API; declara que no observa trabajos de fondo.

Estos puntos son evidencia de código o de la pantalla observada. No prueban por sí solos integración efectiva con todos los servicios.

## Hallazgos visuales de escritorio

1. **El chat inicial queda muy vacío.** En la vista en blanco, el encabezado y las acciones de inicio quedan agrupados arriba y el espacio central domina la pantalla. Una guía de primer uso con ejemplos de tareas seguras y visibles podría orientar al usuario sin enviar mensajes ni iniciar herramientas automáticamente.
2. **La barra inferior pierde legibilidad por truncamiento.** Aun a 1920 px, algunos valores de Memoria y Proveedores se cortan; no se puede leer el estado completo sin abrir los detalles. Conviene reducir duplicidad entre etiqueta y valor, dar ancho al valor prioritario y conservar el detalle expandible como segundo nivel.
3. **La carpeta activa no queda reconocible en la primera mirada.** El panel indica “Carpeta de trabajo”, pero la captura no presenta una ruta clara; además señala que no hay rutas para este turno. Debe diferenciarse visualmente la carpeta vinculada al proyecto, la carpeta seleccionada y las rutas autorizadas para un envío.
4. **La jerarquía del panel derecho es funcional, pero densa.** El historial comparte una columna estrecha con el panel de proyecto. Mantener el desplegable, pero mejorar los títulos, el estado de selección y la acción de cambio de carpeta ayudaría a reducir ambigüedad.

## Medición DOM en móvil

En la misma instancia 8093, a 390 × 844, el documento no presenta overflow horizontal (`scrollWidth == 390`). Sin embargo, `.control-chat-sidebar` empieza en `y=791` y mide 348 px de alto, por lo que casi todo el panel derecho queda debajo del viewport inicial; la barra inferior ocupa `y=793..844`. Esto requiere revisar la composición móvil del panel para que proyecto e historial puedan abrirse y usarse sin quedar fuera de pantalla. Es una medición DOM, no una validación visual móvil ni una prueba de la candidata de PR.

## Revisión posterior de la candidata en escritorio

El 26 de octubre se levantó esta rama en un entorno aislado: Vite `5194` y API `8097`, procesos `31076` y `33788`, respectivamente. El código se sirvió desde el worktree `fix/project-workspace-chat-isolation-20261026`; los datos, la base de conversaciones y dos carpetas de proyecto sintéticas quedaron bajo Temp. No se usaron 8093/8098 ni se invocó ningún proveedor. El endpoint `/api/integration-preview-identity` no existe en esta candidata (404); identidad se acotó por ruta de lanzamiento, PIDs, HEAD `d8093d5` y hashes de los archivos modificados que constan en el registro de verificación del Sprint 16.

La prueba visual encontró que el proxy Vite con `changeOrigin: true` hacía que el servicio rechazara los planes de carpeta con `Origen no permitido`. Tras conservar el `Host` original en el proxy, la interfaz preparó y aplicó planes de carpeta con confirmación humana. Se verificó que:

- El destino del plan era exactamente la carpeta elegida. Se crearon los tres documentos `.bago` y `.workspace-service/manifest.json`; la respuesta confirmó el binding activo y los cuatro archivos aparecen en el recibo.
- Un segundo proyecto se creó en una carpeta distinta. El chat vacío se creó mediante la acción explícita «Nueva» en el primer proyecto. El segundo proyecto devolvió una lista vacía; al volver al primero, la interfaz mostró de nuevo ese chat.
- Los recibos de ambos proyectos quedaron `APPLIED`; al volver a activar el primero, el plan preservó sus archivos existentes y no creó copias.

Captura sintética del panel de proyectos y el selector de carpeta: [workspace-projects-candidate.png](../../.bago/evidence/frontend-review-project-workspace-20261026/workspace-projects-candidate.png). SHA-256: `E40BC66B486DB11174D82200FD135048692E7217C2495CF9AE10069B30DC0E87`.

La barra inferior indica solicitudes HTTP **activas en este momento**, no un contador acumulado: `0 solicitudes activas` significa que el backend está inactivo. Se ajustó esa etiqueta para que no se interprete como historial de llamadas. La monitorización sigue sin observar trabajos de fondo ni la actividad del host Codex. La vista de escritorio conserva mucho espacio vacío en el chat inicial y el texto pequeño del pie todavía puede ganar tamaño y peso. Esta prueba live sólo verifica el flujo de workspace/chat en el entorno sintético; no acredita el runtime publicado 8093/8098 ni una ejecución larga con Jaeger.

## Revisión renderizada adicional de escritorio y móvil

Se repitió la inspección de la misma candidata aislada con Python Playwright, porque el conector visual no tenía navegadores disponibles. La página `http://127.0.0.1:5194/` devolvió HTTP 200, título `BAGO · Espacio de trabajo`, contenido visible y ningún error de consola o excepción JavaScript. A 1920 × 1080 no hubo overflow. Al navegar desde la barra izquierda a Capacidades, el catálogo terminó de cargar y mostró las capacidades documentales; no se quedó en el estado de carga.

A 390 × 844 tampoco hubo overflow horizontal del documento. El panel de proyecto abierto ocupa el ancho disponible y desplaza visualmente el chat; su botón «Cerrar» lo pliega y deja visible el compositor, con ancho útil de 332 px. El flujo es usable, aunque el panel abierto domina la primera pantalla móvil. El pie contiene 1074 px de indicadores en una franja de 390 px, con desplazamiento horizontal interno; Git y Proveedores quedan fuera de la primera vista y no hay una señal clara de que se pueda deslizar. La captura de escritorio inicial muestra además la etiqueta `New conversation` en inglés con la interfaz española. Conviene localizarla, dar una pista visible del desplazamiento y decidir si el panel debe abrir plegado en móvil.

Capturas de esta pasada, con datos sintéticos, guardadas fuera del repositorio en `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\adl-review-candidate-20261026-e3e72364\frontend-final-desktop.png` y `...\frontend-final-mobile.png`. Se comprobó también la navegación a Capacidades, que mostró el catálogo; sin envíos, cambios de datos ni llamadas a proveedores.

## Pendientes recomendados por prioridad

### P0 - antes de afirmar integración del producto

- Conectar el historial de trabajo con ejecuciones reales y mostrar al menos un recorrido largo exitoso con recibos y traza Jaeger enlazados. Hoy el frontend puede presentar un índice de fuentes, pero la disponibilidad real depende del backend.
- Repetir la comprobación de workspace/chat en el runtime que el usuario vaya a comparar en 8093/8098, tras publicar el candidato; la verificación 5194/8097 es aislada y sintética. La candidata tampoco expone el endpoint `integration-preview-identity`.

### P1 - completar la experiencia de operación

- El indicador “Actividad ADL” debe incorporar un contrato de progreso de jobs/task runs, no sólo peticiones HTTP, y presentar fase, duración y resultado. Hasta entonces debe conservar el rótulo limitado actual.
- Hacer visible qué fuente del historial está ausente o parcial y permitir abrir el registro relacionado, el recibo y la traza desde la misma ficha.
- En proveedores, separar con claridad proveedor registrado, habilitación para el orquestador/agente, modelo elegido y respuesta realmente verificada. El código actual del pie indica que sólo lee metadatos, lo cual es correcto pero insuficiente para diagnosticar disponibilidad.
- Proporcionar una orientación inicial no ejecutable en el chat vacío, con ejemplos cortos para workspace, consulta documental y uso de agentes.

### P2 - pulido y accesibilidad

- Ajustar la distribución de la barra inferior con nombres y valores legibles en escritorio; añadir una señal de desplazamiento o una composición compacta para móvil, donde Git y Proveedores quedan fuera de la primera vista. Probar también zoom del navegador.
- Completar QA de teclado/foco y táctil para el panel derecho, los menús desplegables y el cambio de proyecto; la comprobación visual móvil 390 × 844 sólo cubrió el estado inicial y el cierre del panel.
- Localizar `New conversation` y valorar iniciar el panel de proyecto plegado en móvil para que el chat sea visible desde la primera pantalla.
- Añadir capturas de producto con datos sintéticos y runtime identificado en los manuales de cada caso de uso. No reutilizar capturas locales con datos de conversación reales.

## Dictamen

El frontend está más integrado que un conjunto de pantallas informativas: enlaza chat, capacidades, proyecto, historial de conversaciones, historial de trabajo y estado runtime. Aún falta cerrar la prueba extremo a extremo con la instancia exacta y mejorar la legibilidad inicial de chat, workspace y barra inferior. Evaluación global: `NOT_VALIDATED`; no es un GO para release.
