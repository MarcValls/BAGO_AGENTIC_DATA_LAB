# W01 — Backend Capability Manager

## Estado y alcance

**EXECUTED** en el worktree `codex/conversation-library-v1`, HEAD de base `69b4f4b1ead2552b527e6e48868ab36cc2b38cbc`. El worktree ya estaba sucio; no se limpiaron, revirtieron ni reemplazaron cambios preexistentes. Las escrituras de fuente de W01 se limitaron a `src/capabilities/**`, `src/api/server.py` y `tests/test_capability_manager.py`.

Se añadió un inventario propiedad del backend y una API persistente de propuestas. El almacén SQLite predeterminado vive bajo `%LOCALAPPDATA%/BAGO/AgenticDataLab/capabilities/<workspace-id>/capabilities.sqlite3`; el ID es un hash opaco de la raíz resuelta del workspace. Las consultas filtran por ese ID incluso si se inyecta una ruta de base de datos compartida en pruebas. No se guardan credenciales.

## Inventario expuesto

- `workspace.read_text`: `AVAILABLE`, lectura UTF-8 de archivo individual y rango acotado, solo lectura y requiere opt-in del usuario por turno.
- `mcp.execute`: `UNAVAILABLE`, módulo MCP presente pero sin registry/API de producto conectado.
- `sandbox.execute`: `UNAVAILABLE`, gateway/sandbox presentes pero sin conexión al Agent Runner del producto.
- `agent.run`: `UNAVAILABLE` / `FAIL_CLOSED`, conserva el comportamiento `execution_unavailable`.

Cada entrada presenta efecto, estado, límites, huellas SHA-256 de sus fuentes y fingerprint de catálogo. El catálogo declara expresamente que disponibilidad no equivale a autorización ni ejecución. No se infirió capacidad a partir de los perfiles bajo `agents/`.

## Endpoints y autoridad

- `GET /api/capabilities`: catálogo actual del workspace.
- `GET /api/capabilities/proposals`: propuestas del workspace con filtro de estado y límite estricto.
- `POST /api/capabilities/proposals`: crea una propuesta tipada con ID de capacidad conocido, fingerprint del catálogo, efecto tomado del servidor, alcance y resumen legibles, conversación opcional, revisión inicial y expiración de siete días.
- `POST /api/capabilities/proposals/{id}/cancel`: cancelación explícita con revisión optimista. Las propuestas expiradas pasan a `EXPIRED` y se registra evento.

Los eventos `PROPOSED`, `CANCELLED` y `EXPIRED` son append-only en la API. Validación rechaza campos extra, IDs desconocidos, estados/revisiones inválidos, campos vacíos y patrones conocidos de credenciales. El modelo no tiene una herramienta de propuestas: una salida arbitraria `capability.create_proposal` se rechaza por el dispatcher actual y no crea registros.

**No se crean ni cambian permisos, assignments, tools, `Permit`, jobs, procesos o recibos; no se llama a `SandboxManager`/`ExecutionGateway`; no se toca `/ws/agents/run`.** Cancelar o expirar una propuesta no ejecuta nada. La identidad del actor no está autenticada por este MVP local, por lo que no existe flujo de aprobación.

## Evidencia de verificación

Comandos ejecutados en el candidato:

1. `& .\\.venv-ollama-spiral\\Scripts\\python.exe -m pytest -q tests\\test_capability_manager.py tests\\test_conversation_library.py tests\\test_agent_chat_trace.py` — **PASS, 17 passed**.
2. `& .\\.venv-ollama-spiral\\Scripts\\python.exe -m py_compile src\\capabilities\\__init__.py src\\capabilities\\manager.py src\\api\\server.py tests\\test_capability_manager.py` — **PASS**.
3. `git diff --check -- src\\api\\server.py src\\capabilities tests\\test_capability_manager.py` — **PASS**.
4. `python .goals\\ADL-CAPABILITY-MANAGER-001\\implementation-runtime\\.codex-team-kit\\scripts\\teamctl.py --root .goals\\ADL-CAPABILITY-MANAGER-001\\implementation-runtime verify` — **PASS** para el estado del equipo antes del handoff.

La suite enfocada comprobó API por FastAPI `TestClient`, creación/listado/cancelación, rechazo de inputs, expiración, revisión, persistencia tras reabrir SQLite, aislamiento de dos workspaces, ausencia de cambios en jobs y rechazo de propuesta intentada mediante salida arbitraria de herramienta. Las pruebas inyectan una base SQLite bajo `tmp_path`; no acceden al almacén real de LocalAppData.

El primer `pytest` usando el Python global no pudo recopilar porque ese intérprete no tenía FastAPI. Se repitió con `.venv-ollama-spiral`, y la verificación final pasó. El entorno emite una advertencia de compatibilidad de `langchain_core`/Pydantic v1 al usar Python 3.14. No se ejecutó la suite completa ni un servidor externo real. La skill específica `plugins/bago-agent-decision-engineering-team/skills/backend-engineer/SKILL.md` no existe en este checkout; se siguieron la skill `bago-workers`, el perfil `bago_implementation_worker.toml`, `AGENTS.md`, el protocolo BAGO y el contrato W04 disponibles.

## Riesgos y siguiente consumidor

- W02 debe conectar UI/chat a estos endpoints manteniendo los comandos mutables detrás de interacción explícita de UI. El modelo no debe llamar a `POST` desde texto/tool output.
- Este incremento no constituye aprobación humana autenticada ni ejecución gobernada. Runner debe seguir deshabilitado.
- Pruebas de UI/build, suite completa, instalación, migración de una base preexistente, servidor vivo y seguridad multiusuario: **NOT_RUN**.
- Aplican los hallazgos al worktree sucio auditado, no al commit limpio de base aisladamente.
