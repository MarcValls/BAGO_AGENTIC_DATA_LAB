# W02 — Verificación independiente: persistencia READ/WRITE tras reconstruir el servicio

## Identidad y evidencia

- Misión: `ADL_PROJECT_PERMISSION_RESTART_20261027`.
- Repositorio/candidato Git: branch `codex/adl-project-permission-restart-20261027`; base y HEAD verificado `6f6b972d9923659713015654b4cda01bc772fddf`.
- Identidad TeamCtl: candidate_id `9bdf09833dd28ab922485c21a23e0f645efb5cb812712150dd3c1b07d4f8fada`; scope_sha256 `0af844db09c04531999970ed71e0bce9ed1f51245b48416d0453a7bc7cef9df9`.
- Test: `tests/project-permissions/backend/test_project_permissions.py`; SHA-256 `a570cb08394b90964cf9395dfd6b74c682a28270ca78c9f39023ecda783d2ceb`.
- Nodo ejecutado: `test_saved_read_write_permissions_load_in_fresh_service_instance` — PASS (1 passed, 0.16 s).
- Check TeamCtl: `independent_focused_test`, execution_id `9e9ee2b31fbe43ebb0df12b69b5afa05`, receipt `.bago/team/runtime/executions/9e9ee2b31fbe43ebb0df12b69b5afa05/receipt.json`; result PASS, returncode 0. El stdout gestionado está en `docs/verification/project-permission-restart-r10/focused_test_output.txt` con SHA-256 `b41b012fc87704d1a7b3aa26f2854f145a95eeea21ad2dc524cd1c9738d20868`.

## Cobertura comprobada

El test crea un proyecto sintético con `docs` y `outputs`, guarda READ para `docs` y WRITE para `outputs` usando una instancia de `ProjectPermissions`, luego construye otra instancia sobre el mismo contexto raíz/identidad. La segunda instancia carga el snapshot persistido y compara estado, project_id, root, binding, revision y ambas listas de permisos; después obtiene leases READ y WRITE con la revisión esperada.

La implementación inspeccionada persiste la política en `.bago/state/PROJECT_PERMISSIONS.json`; `snapshot()` vuelve a cargarla mediante `_load()`, que valida serialización canónica, esquema, identidad del proyecto, raíz física, revisión y listas antes de exponer el snapshot. `lease()` vuelve a cargar y validar la política antes de conceder IO.

## Dictamen y límites

P0=0, P1=0, P2=0 observados en este alcance. El resultado demuestra la recarga desde disco al crear una nueva instancia de servicio dentro del test. No demuestra un reinicio real del servidor/proceso BAGO ni persistencia entre sesiones de una aplicación en ejecución.

NOT_RUN: servidor real reiniciado, integración API/UI, suite completa y cualquier test distinto del nodo indicado.
