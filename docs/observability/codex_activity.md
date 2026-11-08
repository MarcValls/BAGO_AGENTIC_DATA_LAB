# ADL — Observador de actividad Codex (candidato 0.1)

## Propósito

Permitir que Codex desarrolle ADL mientras ADL observa una parte de su propia actividad. La observación no es ejecución gobernada, no autoriza acciones y no acredita autonomía ni éxito de tareas.

Se reutilizan los contratos ya disponibles en ADL: src/observability/local_trace.py como evidencia y src/observability/otel_bridge.py como proyección a OpenTelemetry/Jaeger. No se crea un segundo Jaeger ni una fuente de autoridad paralela.

## Arranque optativo en Windows

Requisitos: dependencias de requirements.txt instaladas en el Python de ADL, Codex CLI en PATH y, para visualizar trazas, Jaeger local con OTLP/HTTP 4318 y UI 16686. Comprueba el contenedor existente antes de levantar otro.

Desde la raíz del repositorio, iniciar una **nueva** sesión Codex observada:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\INICIAR_CODEX_ADL_OBSERVADO.ps1

El lanzador arranca un receptor HTTP OTLP de **logs** en 127.0.0.1:4319, con almacén local en .bago/traces/codex-activity (ignorado por Git), y abre Codex con las opciones de exportador solo para ese proceso. También configura las trazas nativas de Codex directamente a Jaeger mediante 127.0.0.1:4318/v1/traces. Al terminar Codex, detiene únicamente el receptor que creó y presenta el diagnóstico. No modifica la configuración global Codex, no se engancha a sesiones anteriores y no reinicia Jaeger.

Mientras Codex trabaja, en otra terminal:

    python scripts/codex_activity.py report

Al cerrar una fase, exportación **explícita** de una instantánea observada:

    python scripts/codex_activity.py project

El comando project exporta como máximo los últimos 500 eventos (opción --limit, rango 1..1000) con un service.name separado: adl-codex-activity. La respuesta diferencia cantidad total observada, cantidad exportada y eventos antiguos excluidos. Para comprobar la recepción, consulta Jaeger (UI/API), no confundas el recibo de exportador con un readback del collector.

## Uso por Codex durante el desarrollo

Instrucción para incorporar al encargo de Codex:

> Trabaja en ADL desde el lanzador observado. Al iniciar y cerrar cada fase de implementación o pruebas consulta python scripts/codex_activity.py report. Usa hallazgos y event_id como evidencia diagnóstica, nunca como permiso ni prueba de corrección. Diferencia NO_DATA de inactividad. Si hay P1, examina el hecho original. Conserva resultados PASS/FAIL/NOT_RUN con la identidad de la candidata. Solo ejecuta project si su efecto de exportación está autorizado. No modifiques ni fuerces el monitor existente ni el colector Jaeger para lograr una apariencia de éxito.

No hay un bucle autónomo de remediación: Codex lee el diagnóstico como cualquier otra evidencia, sin darle autoridad adicional.

## Contrato y limitaciones

Entrada: protobuf ExportLogsServiceRequest, Content-Type application/x-protobuf, 2 MiB y 2.000 registros por lote. El receptor solo acepta servicio Codex y una lista de eventos identificables. Persistencia: JSON por evento con creación exclusiva, hash de integridad, pseudónimos de sesión/llamada y campos permitidos. Los contenidos de prompts, parámetros, respuestas de herramientas, credenciales e identidad no se almacenan; la telemetría original pasa por memoria del receptor mientras se filtra. La API se vincula solo a loopback.

El estado de cobertura es siempre PARTIAL. Una hora sin eventos NO demuestra inactividad. No se infieren procesos, PIDs, descendencia ni relaciones causa-efecto a partir de proximidad temporal. Las instantáneas de Jaeger crean spans observacionales sin relación padre-hijo inventada ni duración de operación inferida. Las trazas nativas de Codex y los spans ADL tienen identidades independientes.

Reglas deterministas iniciales: TOOL_FAILURE_OBSERVED (P1), SLOW_TOOL_REPORTED (P2), TOOL_DECISION_NOT_APPROVED (informativo), WITNESS_INTEGRITY_UNREADABLE (P1). P1 significa prioridad de examen, no fallo demostrado de ADL. Ningún diagnóstico inicia automáticamente reparación o permiso.

**NO_RECUPERADO:** código/contrato del monitor de procesos de la captura. Por tanto, la correlación herramientas–PID–recibos y el análisis de 2.415 procesos no forman parte de este candidato. Tampoco se ha comprobado que la versión local de Codex acepte estos parámetros de telemetría.

## Pruebas y aceptación

- Prueba local de candidato: python -m pytest -q tests/test_codex_activity_monitor.py
- Hay que comprobar en Windows que un Codex real emite eventos que el receptor reconoce durante una ejecución de desarrollo.
- Hay que consultar Jaeger y obtener los IDs reales de las trazas, no solo el resultado PASS de exportación.
- Hay que comprobar que la caída del collector no rompe la ejecución Codex, que los datos confidenciales no se exportan en logs y que los límites se cumplen.
- Antes de cerrar el trabajo de ADL deben ejecutarse la suite completa, los comandos de generación/comprobación README y las verificaciones de coordinación previstas en AGENTS.md. No se han ejecutado en el entorno local del usuario.

La integración se mantiene optativa hasta superar esas comprobaciones.
