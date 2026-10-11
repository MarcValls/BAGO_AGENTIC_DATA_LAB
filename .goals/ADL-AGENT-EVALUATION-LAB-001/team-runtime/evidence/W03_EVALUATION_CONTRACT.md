# W03 - Contrato de Agent Evaluation Lab

## Identidad

- Misión: `ADL_AGENT_EVALUATION_LAB_SPIRAL_001`.
- Candidato: `codex/adl-agent-evaluation-lab-20261010`.
- HEAD de inspección: `1e4d9f930da1225ce61ce27def897f76d57a08fc`.
- Base de la síntesis: W01 backend map y W02 product/UX map, ambos con handoffs verificados.
- Esto define implementación: aún no implica producto ejecutado ni validado.

## Hechos observados

- ADL ya tiene conversación persistente, selección de agentes, configuración/listado de modelos Ollama, LocalTrace y correlación Jaeger opcional.
- El Evaluator actual puntúa cobertura de gobernanza/recibos de un agente tipado; no evalúa el texto de respuesta del chat.
- El Agent Runner de producto sigue fail-closed. Este incremento no debe convertir evaluación de chat en ejecución de trabajos.
- La matriz de habilidades del repo marca evaluación como prioridad, pero no es por sí misma evidencia de demanda externa.
- Verificación de proveedor en el entorno actual: `ollama-cloud`, auth `api_key`, modelo configurado `gemma4:31b`; status `configured_unverified`, descubrimiento devolvió `model_available=true` y `generation_performed=false`. No se ejecutó inferencia durante W01/W02.

## Contrato del MVP

### Producto

Añadir una vista **Agent Evaluation Lab**, separada de la evaluación de artefactos demo. Desde la vista se podrá:

1. Elegir un agente existente y un modelo que Ollama haya reportado en el catálogo del proveedor.
2. Crear y editar una suite versionada con nombre y hasta 10 casos.
3. Cada caso contiene un prompt de usuario, una lista `must_include` y `must_not_include`, con límites de longitud. Las reglas son datos de evaluación, no instrucciones operativas.
4. Revisar el número de llamadas y pulsar **Run evaluation** explícitamente. Cada caso hace una llamada individual de una sola ronda al proveedor; no usa historial de chat, herramientas, lectura del workspace ni ejecución de trabajos.
5. Ver por run suite + versión, agente + fingerprint de configuración, provider/model, estado, duración, IDs, casos/checks y salida para inspección. Los runs son inmutables; editar la suite incrementa su versión.
6. Retener trace local por caso; mostrar enlace Jaeger únicamente si una exportación confirmó la correlación. Fallos del proveedor y trazas ausentes quedan explícitos; nunca se sustituyen por fixtures.

### Evaluación y resultado

- Checks MVP: respuesta no vacía, texto incluido/excluido según las reglas exactas insensibles a mayúsculas y presencia de identidad trace para respuestas completadas.
- El score es porcentaje de checks declarados superados; no es score universal de calidad, factualidad, seguridad o satisfacción.
- No incluir LLM-as-judge en este primer incremento; por lo tanto no hay segunda inferencia ni costo oculto.
- Provider cost/tokens: `NOT_REPORTED` hasta que la respuesta oficial del proveedor los exponga; `0.0` no puede utilizarse para declarar gasto cero.
- En un error antes de respuesta debe persistirse `ERROR`, clase de error segura y duración. No se guarda cuerpo de excepción ni credenciales.

### Datos y autoridad

- Persistir suite y runs en SQLite local fuera del checkout, aislado por workspace como la biblioteca de conversaciones.
- Un run conserva un snapshot de la suite/case y el fingerprint del agente/modelo usado; editar la suite o perfil no reescribe el histórico.
- Nunca serializar API keys/tokens. Los prompts, aserciones y salidas pertenecen al usuario y se retienen localmente; documentar ubicación y eliminación.
- Las suites no se envían a herramientas/chat-control como autoridad, no crean permisos y no alteran perfiles de agente.

### API y trazabilidad

- Endpoints backend para listar/crear/versionar suites, listar historial y ejecutar por IDs validados.
- El backend recarga agente y catálogo de modelos; no confía en identidad/config/prompt de agente enviada por browser.
- Cada caso genera `evaluation_run_id`, `suite_id`/versión, `case_id`, `agent_id`, `agent_config_fingerprint`, `provider_id`, `model_id` y `trace_id`.
- LocalTrace omite prompt y salida. Attributes adicionales sólo serán IDs, huellas, estado, duration y metric metadata no sensible.
- El catálogo `GET /api/capabilities` añade `agent.evaluate` únicamente cuando la ruta realmente está conectada; declarar que cada caso envía una inferencia explícita a Ollama y no habilita efectos workspace.

## Mercado y alineación con perfil

El [State of Agent Engineering de LangChain (12-jun-2026)](https://www.langchain.com/state-of-agent-engineering) encuestó a más de 1.300 profesionales; reporta calidad como bloqueo principal (32%), observabilidad en 89%, offline evals en 52,4% y online evals en 37,3%. El [State of SRE Report 2026 de Dynatrace](https://www.dynatrace.com/resources/ebooks/sre-report/) reporta que monitorizar rendimiento y precisión de modelos está entre las prioridades de ingeniería de plataforma/SRE. LinkedIn indica que LLM proficiency, revisión de código y documentación técnica están creciendo en los roles de ingeniería, y que AI literacy aparece entre habilidades crecientes en España ([Skills on the Rise 2025](https://www.linkedin.com/business/talent/blog/learning-and-development/skills-on-the-rise)). Estos informes no predicen una contratación particular: justifican priorizar una demostración de evaluación, fiabilidad, observabilidad y gobernanza frente a añadir otra demo de chat.

Siguiente capacidad de la hoja de ruta: **agentes de una ejecución y agentes activados por señal**. Mantenerla `PROPOSED` hasta que el runner, trigger identity, scheduling/event ingestion, policy y receipts puedan ser ejecutados y verificados; el MVP de evaluación no pretende cubrirla.

## Criterios de aceptación del candidato

1. Suite y runs persisten con control de revisión; no se filtran a repositorio, logs/jaeger, clave ni archivos del workspace.
2. Un test de contrato con proveedor sustituido prueba creación/edición, casos inválidos, aserciones, historial, error de proveedor y correlación de trace sin fingir una llamada real.
3. Frontend build/lint disponible y accesibilidad básica/navegación revisada; ejecución del producto muestra suite, modelo, número de llamadas y resultados explícitos.
4. Una inferencia real de un caso sintético con el Ollama Cloud configurado registra respuesta, `gemma4:31b`, métrica de duración, resultado de reglas y `trace_id`. Jaeger se reclama sólo si la exportación y consulta demuestran el trace.
5. Evidencia ligada a HEAD final y separada por `fixture tests`, `real inference`, `Jaeger export`, `NOT_RUN`.
6. No merge, push o commit dentro de este goal.

## Decisión de alcance

`GO` para Agent Evaluation Lab acotado a respuestas single-turn reales, reglas deterministas escritas por la persona, persistencia local y telemetría correlacionada. No habilitar ejecución general de agentes, evaluación semántica automática, comparaciones automáticas, online evals, coste tokens/precio, multi-proveedor ni cambios en Runner.
