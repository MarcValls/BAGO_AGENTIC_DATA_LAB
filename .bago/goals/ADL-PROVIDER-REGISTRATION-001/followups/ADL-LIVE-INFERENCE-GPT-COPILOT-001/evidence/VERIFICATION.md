# Verificación de integración local

Proyecto: ADL en `C:/Users/AMTEC_Terminal_1º/Desktop/BAGO5_ADL`. HEAD base
`76e57ca7dd5f26fd27a40d81324d945ec798c867`, rama `main`, cambios sin commit.
Los archivos ajenos que ya estaban modificados se conservaron. No se publica
una rama ni se cambia la misión Inspector existente.

## Resultado y recorrido

Settings → Proveedores y modelos → OpenAI Platform/GitHub Copilot → guardar →
comprobar acceso → Builder → seleccionar proveedor/modelo → guardar → Chat o
Agent Runner. Los adaptadores usan la credencial del sistema; la confirmación
queda ligada al modelo y a la revisión del registro. Errores de autenticación,
respuestas vacías/malformadas o fallos inesperados eliminan un estado comprobado
anterior. Una respuesta de una configuración anterior no verifica una credencial
reemplazada durante la solicitud.

OpenAI adapta los nombres ADL a nombres de función aceptados por la API,
conserva los identificadores de llamada y serializa los resultados de herramientas.
Copilot solo expone callbacks de captura de propuestas, rechaza permisos del SDK
y detiene su turno al capturarlas. BER mantiene preparación y decisión explícita
antes de cualquier efecto. Las lecturas de chat siguen los permisos ya emitidos.
No hay cambio de proveedor al agotar el bucle de herramientas.

## Comprobaciones finales

| Acción ejecutada | Resultado y alcance |
|---|---|
| `python scripts/generate_dynamic_readme.py` | PASS; 322 tests pasados; README generado desde sus fuentes |
| `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS; 322 casos recogidos, sin volver a ejecutar la suite |
| `npm run test:providers` en frontend | PASS; 4 tests de componentes renderizados en JSDOM, API simulada |
| `npm run build` en frontend | PASS; TypeScript y build Vite, 129 módulos |
| `.venv/Scripts/python.exe -m pip install github-copilot-sdk==0.3.0` | Ejecutado; dependencia instalada en el entorno de ADL |
| Importación/inspección de `CopilotClient`, `SubprocessConfig` y permisos en `.venv` | PASS; versión 0.3.0 y contrato usado por el adaptador disponibles |
| `.venv/Scripts/python.exe -m pytest tests/test_live_agent_providers.py -q --disable-warnings` | PASS; 20 tests, HTTP/SDK simulados; ejecución aprobada después de bloqueo de acceso a temp de pytest |
| Revisión independiente `bago_verifier`: tests de proveedores y Runner | PASS; 43 tests y 4 de interfaz, sin P0/P1/P2 pendientes en el alcance asignado |
| `git diff --check` | PASS; avisos de conversión CRLF en archivos preexistentes |
| `.venv/Scripts/python.exe .../files/runtime_smoke.py` | PASS; HTTP real del backend local, HTML servido igual al build y 3 assets con 200; ver runtime.json |

La primera prueba enfocada encontró un fallo de compatibilidad Ollama (1 fail,
34 pass); se corrigió el uso de su API de texto y se verificó después. La primera
generación completa pasó 320 casos; se repitió sobre el candidato final para
incluir dos regresiones añadidas durante la revisión independiente (322 pass).
Los fallos de consulta de un selector en las pruebas UI se corrigieron antes
del resultado final. No se usan los resultados anteriores como evidencia final.

## Frontera observada y límites

- El backend anterior de este mismo repositorio en 8080 se identificó por ruta,
  proceso y puerto antes de recargarlo. Se comprobó primero un candidato en
  8091; ese proceso temporal quedó detenido. El servidor final escucha solo
  en 127.0.0.1:8080 (PID observado 44328).
- La API real anuncia `chat_and_agent_runner` para los dos nuevos proveedores,
  ambos `not_configured`. Las llamadas reales a sus servicios son `NOT_RUN`:
  no hay un registro de cuenta preparado para la comprobación.
- Los tests funcionales verifican el recorrido HTTP y el procesamiento de
  respuestas mediante transportes simulados. No acreditan autenticación,
  disponibilidad de modelos, consumo o inferencia remotos.
- La inspección visual en navegador es `NOT_RUN`: CUA indicó iab no disponible
  y devolvió inventario de navegadores vacío. JSDOM no prueba píxeles,
  responsive ni consola de un navegador real.
- Se conserva la distinción entre OpenAI Platform, Codex CLI y GitHub Copilot.
  Codex y los otros registros no integrados siguen mostrando esa limitación.
- La identidad del candidato está registrada en candidate.json. Los cambios de
  código o build invalidan esta asociación hasta repetir los checks afectados.

## Fuentes técnicas primarias consultadas

- [OpenAI: Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): nombres de funciones y `tool_call_id`.
- [GitHub Copilot SDK: Python](https://github.com/github/copilot-sdk/blob/main/python/README.md): sesión, herramientas y permisos; el contrato efectivo se contrastó con la versión 0.3.0 instalada.
- [GitHub: filtrado de herramientas personalizadas](https://github.com/github/copilot-sdk/issues/1179): razón para usar una lista explícita de callbacks disponibles.
