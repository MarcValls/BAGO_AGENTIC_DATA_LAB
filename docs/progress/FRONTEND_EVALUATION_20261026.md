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

## Pendientes recomendados por prioridad

### P0 - antes de afirmar integración del producto

- Abrir un runtime cuyo `integration-preview-identity` corresponda al commit/candidato exacto y demostrar cambio de workspace, aislamiento de conversaciones por proyecto y persistencia tras recarga.
- Conectar el historial de trabajo con ejecuciones reales y mostrar al menos un recorrido largo exitoso con recibos y traza Jaeger enlazados. Hoy el frontend puede presentar un índice de fuentes, pero la disponibilidad real depende del backend.
- Verificar visualmente las acciones de selección/cambio de workspace en el flujo de creación de proyecto y confirmar que los archivos mínimos se crean bajo la carpeta elegida por el usuario.

### P1 - completar la experiencia de operación

- El indicador “Actividad ADL” debe incorporar un contrato de progreso de jobs/task runs, no sólo peticiones HTTP, y presentar fase, duración y resultado. Hasta entonces debe conservar el rótulo limitado actual.
- Hacer visible qué fuente del historial está ausente o parcial y permitir abrir el registro relacionado, el recibo y la traza desde la misma ficha.
- En proveedores, separar con claridad proveedor registrado, habilitación para el orquestador/agente, modelo elegido y respuesta realmente verificada. El código actual del pie indica que sólo lee metadatos, lo cual es correcto pero insuficiente para diagnosticar disponibilidad.
- Proporcionar una orientación inicial no ejecutable en el chat vacío, con ejemplos cortos para workspace, consulta documental y uso de agentes.

### P2 - pulido y accesibilidad

- Ajustar la distribución de la barra inferior con nombres y valores legibles en escritorio; probar tamaños estrechos y zoom del navegador.
- Completar QA de teclado/foco y móvil para el panel derecho, los menús desplegables y el cambio de proyecto.
- Añadir capturas de producto con datos sintéticos y runtime identificado en los manuales de cada caso de uso. No reutilizar capturas locales con datos de conversación reales.

## Dictamen

El frontend está más integrado que un conjunto de pantallas informativas: enlaza chat, capacidades, proyecto, historial de conversaciones, historial de trabajo y estado runtime. Aún falta cerrar la prueba extremo a extremo con la instancia exacta y mejorar la legibilidad inicial de chat, workspace y barra inferior. Evaluación global: `NOT_VALIDATED`; no es un GO para release.
