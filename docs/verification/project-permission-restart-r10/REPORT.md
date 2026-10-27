# W02 — Verificación independiente: persistencia READ/WRITE tras reconstruir el servicio

## Identidad y evidencia

- Misión: `ADL_PROJECT_PERMISSION_RESTART_20261027`.
- Repositorio/candidato Git: branch `codex/adl-project-permission-restart-20261027`; base `6f6b972d9923659713015654b4cda01bc772fddf`; HEAD candidato ejecutado `c1b1fce16a6306516531602488072c7fd20ab36b`.
- Identidad TeamCtl: candidate_id `9bdf09833dd28ab922485c21a23e0f645efb5cb812712150dd3c1b07d4f8fada`; scope_sha256 `0af844db09c04531999970ed71e0bce9ed1f51245b48416d0453a7bc7cef9df9`.
- Test: `tests/project-permissions/backend/test_project_permissions.py`; SHA-256 `a570cb08394b90964cf9395dfd6b74c682a28270ca78c9f39023ecda783d2ceb`.
- Nodo ejecutado: `test_saved_read_write_permissions_load_in_fresh_service_instance` — PASS (1 passed, 0.16 s).
- Check TeamCtl: `independent_focused_test`, execution_id `9e9ee2b31fbe43ebb0df12b69b5afa05`, receipt `.bago/team/runtime/executions/9e9ee2b31fbe43ebb0df12b69b5afa05/receipt.json`; result PASS, returncode 0. El stdout gestionado está en `docs/verification/project-permission-restart-r10/focused_test_output.txt` con SHA-256 `b41b012fc87704d1a7b3aa26f2854f145a95eeea21ad2dc524cd1c9738d20868`.

## Comprobación de reinicio del proceso BAGO (runtime aislado)

- Candidato ejecutado: el checkout de este PR, HEAD `c1b1fce16a6306516531602488072c7fd20ab36b`.
- Servicio local aislado: `127.0.0.1:8101`; `data-root` separado en `C:\BAGO_TESTS\ADL_PERMISSION_LIVE_RESTART_20261027\data`.
- Proyecto sintético seleccionado: `C:\BAGO_TESTS\ADL_PERMISSION_LIVE_RESTART_20261027\workspace`, `project_id=workspace_36b71a88b76c45c69712c9f6b6e13978`.
- La política se guardó antes del reinicio con READ y WRITE sobre `.`. El proceso aislado anterior (PID `25500`) se detuvo; se comprobó que el puerto 8101 dejó de escuchar; después se inició el mismo candidato y raíz de datos con PID `107764`.
- Después del reinicio, `/api/health` respondió `ok`; `/api/project-folders/v1/active` devolvió el mismo `project_id` y raíz; `/api/project-permissions` devolvió `state=configured`, la misma raíz y revisión `76d067bcd10a5ddd8dd727cc489b8cc4400255f651b13821c5c5d67666cf64a6`, y READ/WRITE `.`. La revisión coincide con SHA-256 de `.bago/state/PROJECT_PERMISSIONS.json` del proyecto.
- Observación final: `2026-10-27T10:57:36.5541679Z`; respuesta resumida y hash en `live_restart.json`.

Esto demuestra que la selección del proyecto y sus permisos sobreviven a un reinicio real del proceso BAGO en un runtime aislado. El alcance del permiso es la raíz del proyecto seleccionado, separada de la carpeta de código de ADL.

## Cobertura comprobada

El test crea un proyecto sintético con `docs` y `outputs`, guarda READ para `docs` y WRITE para `outputs` usando una instancia de `ProjectPermissions`, luego construye otra instancia sobre el mismo contexto raíz/identidad. La segunda instancia carga el snapshot persistido y compara estado, project_id, root, binding, revision y ambas listas de permisos; después obtiene leases READ y WRITE con la revisión esperada.

La implementación inspeccionada persiste la política en `.bago/state/PROJECT_PERMISSIONS.json`; `snapshot()` vuelve a cargarla mediante `_load()`, que valida serialización canónica, esquema, identidad del proyecto, raíz física, revisión y listas antes de exponer el snapshot. `lease()` vuelve a cargar y validar la política antes de conceder IO.

## Dictamen y límites

P0=0, P1=0, P2=0 observados en este alcance. El test focalizado demuestra recarga desde disco al crear otra instancia del servicio; la comprobación HTTP independiente demuestra además persistencia tras reiniciar el proceso en un runtime aislado.

NOT_RUN: lectura mediante el modelo/proveedor después del reinicio, operaciones de edición/copia/renombrado después del reinicio, recorrido UI, runtime del usuario y suite completa local. Las operaciones edit/copy/rename con flujo gobernado y revisión humana tienen evidencia histórica separada en `docs/verification/project-file-operations-r9/REPORT.md`, ejecutada en otro proyecto sintético; no se atribuyen a esta prueba de reinicio.
