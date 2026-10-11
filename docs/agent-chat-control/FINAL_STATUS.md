# Agent Chat Control Plane — estado final de la primera entrega

## Estado del candidato

- Resultado: **VERIFIED en análisis estático y build**; runtime e integración con Ollama: **NOT_RUN**.
- Rama: `codex/agent-chat-control-v1`.
- Worktree aislado: `C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\BAGO_AGENTIC_DATA_LAB_chat_control`.
- HEAD base: `4d6a0a95932cb4167b8f6a8caa6fdfcd79f4abff`.
- Fingerprint del candidato (90 archivos relevantes): `1e57cd050d9940c9bb2311df384f6f3397b14229b99b3443729f86127dc9376f`.
- Revisión independiente: AC04 PASS, 0 P0, 0 P1, 1 P2; informe en `docs/agent-chat-control/verification/AC04-review.md`.

## Entregado

- El chat es la pantalla inicial; Inspector y las vistas de portfolio siguen accesibles desde la navegación.
- Ajustes permiten escoger API key de Ollama Cloud o sesión local de Ollama CLI. La clave es write-only y se guarda mediante el almacén de credenciales del sistema operativo.
- El chat lista agentes, crea una propuesta revisable y solo la guarda tras confirmación explícita. Cada agente puede tener una conversación Ollama real cuando el proveedor está configurado.
- Registros de agentes heredados sin `provider_id`/`model_id` y con ID corto compatible aparecen sin migración; el modelo seleccionado solo se usa para esa petición.
- La API y los puertos publicados quedan en loopback; CORS y todos los WebSocket requieren origen local permitido. Los datos Docker de agentes/configuración no secreta/trabajos se persisten en volúmenes.
- En Docker, los ajustes del proveedor se deshabilitan porque el contenedor no puede usar de forma segura el almacén de credenciales del host ni el Ollama local. El lanzamiento compatible en Windows está en `scripts/run-local-ui.ps1`, con instrucciones en `docs/agent-chat-control/LOCAL_SETUP.md`.
- El Runner heredado ahora devuelve `execution_unavailable`: no crea jobs, no emite éxito simulado ni registra métricas inventadas.

## Verificación ejecutada

- `npm run build`: PASS; TypeScript/Vite, 126 módulos.
- `python -m compileall -q src/api/server.py src/providers/ollama.py`: PASS.
- `docker compose -f docker-compose.ui.yml config --quiet`: PASS.
- Parseo AST de `scripts/run-local-ui.ps1`: PASS.
- `git diff --check`: PASS.
- `.codex-team` `teamctl verify`: PASS para los handoffs de la misión.

## No ejecutado y limitaciones

- No se ejecutó el launcher ni el servidor; no hubo prueba en navegador, handshake WebSocket real, prueba automatizada, acceso al almacén de credenciales, ni llamadas/token spend a Ollama. La disponibilidad del modelo y la cuenta siguen sin verificar.
- El agente heredado `agent_78f9cfd1` permanece intacto en el checkout original. No se copió al worktree; por ello no aparecerá al ejecutar la vista desde este worktree aislado hasta que los cambios se integren en el checkout que contiene ese archivo.
- Hallazgo P2: en modo contenedor, el campo de API key sigue editable aunque el botón guardar esté deshabilitado y el backend rechace la configuración. La clave solo permanecería temporalmente en memoria del componente; no se envía ni persiste.
- Todavía no se pueden encargar trabajos reales a agentes desde el chat. No hay dispatch gobernado conectado; el Runner se cierra hasta que una capacidad autorizada produzca resultado trazable.
- El despliegue LAN sigue sin soporte hasta añadir autenticación de API.
- `npm ci` informó 2 hallazgos en dependencias (1 moderado, 1 alto); no se modificaron los manifiestos para resolverlos.

## Evidencias

- Contrato: `docs/agent-chat-control/contracts/CONTROL_PLANE_V1.md`.
- Revisión independiente: `docs/agent-chat-control/verification/AC04-review.md`.
- Preparación de ejecución local: `docs/agent-chat-control/LOCAL_SETUP.md`.
- Handoffs: `.codex-team/handoffs/AC01.json`, `AC02.json`, `AC03.json`, `AC04.json`, `AC06.json`, `AC07.json`, `AC08.json`, `AC09.json`, `AC10.json`.
- Cambios de contrato: `.codex-team/change_requests/CR-006` a `CR-010`.

Esta misión cierra la primera vertical slice de chat, provider, inventario y creación de agentes. No certifica el objetivo mayor de controlar toda la aplicación desde el chat ni la ejecución de trabajos gobernada.

## Seguimiento de interfaz de creación asistida (2026-10-09)

Se incorporó el patrón del ejemplo existente en BAGO: la IA produce una propuesta, la persona puede editar nombre, descripción, tipo y prompt, selecciona un modelo expuesto como listado por el backend configurado, y confirma o cancela. La selección vacía/no disponible bloquea la creación. Los detalles avanzados aclaran que declarar herramientas no otorga permiso de ejecución. Evidencia y límites actualizados en docs/agent-chat-control/verification/agent-creation-assistance-followup.md. La compilación estática final de este seguimiento pasó; navegador, Ollama y pruebas automatizadas quedaron NOT_RUN. La revisión AC04 y la huella anteriores no cubren este cambio.

## Seguimiento del launcher local: gestión de puertos (2026-10-09)

El launcher recuerda el PID del listener real (incluyendo el proceso hijo que crea Python en Windows) y su hora de inicio; al relanzar, termina solo la instancia propia verificada. Si 8080 pertenece a otro programa, escoge el primer puerto libre y configura ese origen local para HTTP/WebSocket. Verificación observada: 8080 ocupado por Docker/WSL; primer arranque en 8081 con API saludable; segundo arranque terminó el listener anterior y reutilizó 8081 con un PID nuevo; CORS aceptó el origen 127.0.0.1:8081; listener ajeno 8082 quedó intacto. Detalle en docs/agent-chat-control/verification/local-port-reuse-followup.md.

## Demostración live para el videotutorial (2026-10-10)

La nota inicial de runtime `NOT_RUN` describe la verificación de la primera entrega. En una demostración posterior, la UI local respondió a través de Ollama Cloud: el agente persistido **Frontend Auditor**, fijado a `kimi-k2.6`, leyó las líneas 1-8 de un archivo sintético y devolvió una respuesta. La LocalTrace `trace-c7ec5fcc40284a42` registra `provider_id=ollama-cloud`, `outcome=response_received` y el origen leído. El asistente global estaba configurado con `gemma4:31b`; no es el modelo fijado al agente lector.

El [videotutorial](assets/ADL_videotutorial_primer_usuario.mp4) conserva la pantalla completa de ajustes y cubre el campo de API key con una máscara. La [guía y el alcance](TUTORIAL_PRIMER_USO.md) enlazan subtítulos, archivo de entrada y copia de la traza.

Esta evidencia verifica esa lectura acotada y respuesta live. No demuestra auditoría del código del proyecto, modificación de archivos ni ejecución de jobs. La propuesta de agente que aparece en el vídeo se cancela y no se persiste.
