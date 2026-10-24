# Workspace Service 0.1.0 RC1 — contrato previo a implementación

Frontera: módulo Python estándar y CLI sin importar ADL/BAGO. No toca repositorios o cuentas activos. Se requiere raíz padre explícita permitida y solo se administra un workspace NUEVO creado por este módulo, identificado por manifiesto. No se adopta silenciosamente una carpeta existente.

## Alcance finito

WS01 crear workspace y sembrar contexto/estado/continuidad sin sobrescritura. WS02 archivos de texto listar/leer/crear/editar/mover/renombrar/papelera/restaurar/eliminar definitivamente con precondición hash y confirmación estructurada. WS03 Git local estado/diff/rama/stage seleccionado/commit identificado; no stage ajeno ni hooks arbitrarios. WS04 planes remotos revisables y lectura allowlist gh, sin creación/PR/merge remoto. WS05 pruebas reales CLI/repos efímeros, negativos, recuperación y ZIP extraído.

Bloqueados: rutas absolutas de archivo, traversal, symlinks/reparse points, .git, archivos de credenciales, .workspace-service interna; texto máximo 1MiB. La única escritura .bago es la siembra inicial y actualización explícita de los tres archivos sembrados. El borrado definitivo solo actúa sobre una entrada de papelera de este servicio; no ofrece borrado recursivo arbitrario. No prometer defensa frente a un adversario local que sustituya rutas simultáneamente: el servicio no es un sandbox del SO.

## SDK estable

`WorkspaceService(allowed_parent)`; `create(name, title, confirmed=True) -> workspace`; después `open(workspace_id) -> Workspace`.

`Workspace.info()` → `{id,root,name,revision,context_files:[{path,sha256}]}`.
`Workspace.list_files(directory="")` → `{files:[{path,size,sha256}],excluded:[{path,reason}]}`.
`Workspace.read(path)` → `{path,text,sha256,size}`.
`Workspace.write(path,text,expected_sha256,confirmation)` → archivo; expected_sha256=null solo para crear un archivo inexistente.
`Workspace.move(path,destination,expected_sha256,confirmation)` → archivo destino; nunca sobrescribe.
`Workspace.trash(path,expected_sha256,confirmation)` → `{trash_id,path,sha256,revision}`.
`Workspace.restore(trash_id,expected_revision,confirmation)` → archivo original; nunca sobrescribe.
`Workspace.delete_trash(trash_id,expected_revision,confirmation)` → `{deleted:true,trash_id}`.
`Workspace.trash_list()` → `{items:[...]}`.

Confirmación: `{confirmed:true,operation:"write|move|trash|restore|delete_trash|git_init|git_branch|git_stage|git_commit|resolve",workspace_id:ID}`. Cada acción valida operación e identidad, no basta un booleano genérico. API usa `ServiceError(code,message,status)`.

`Workspace.git_status()` → `{head,branch,status,index_fingerprint,worktree_fingerprint,conflicts}`.
`Workspace.git_diff(paths=[],cached=False)` → `{head,diff}`.
`Workspace.git_init(confirmation)` → status (solo nuevo workspace propio).
`Workspace.git_branch(name,expected_head,confirmation)` → status (crea sin checkout).
`Workspace.git_stage(paths,expected_head,expected_hashes,confirmation)` → `{status,selection_revision,paths}`. Índice debe estar vacío; se comprueba archivo y HEAD; no añade otros paths.
`Workspace.git_commit(message,expected_head,selection_revision,confirmation)` → `{commit,head_before,paths,status}`. Solo índice exacto creado por git_stage y bytes aún iguales. Identidad local explícita CLI --author-name/--author-email (por defecto servicio sintético); no utiliza credenciales ni identidad global del usuario.
`Workspace.resolve(path,text,expected_sha256,confirmation)` edita solo archivo conflictivo autorizado y verifica que no quedan marcadores; no stage/commit/ours/theirs implícito.

Git subprocess: argumentos cerrados, shell=False, hooks deshabilitados y sin red; se rechazan filtros, includes de config y otros mecanismos de ejecución en repositorios no creados por el servicio. No se importan repos ajenos. Conflictos no se inventan: tests pueden preparar un merge local deliberado en fixture.

`Workspace.remote_plan(kind,repo,base,head,title)` → plan `{operation,repo,base,head,expected_local_head,status:"PROPOSED",executed:false}`. kind repo_create/pr_create/pr_merge/conflict_review. No ejecución remota disponible en esta candidata.
`github_read(kind, repo=None)` → resultado real `gh auth status`, `gh repo view OWNER/REPO --json ...` o `gh pr list --repo OWNER/REPO --json ...`. No comandos arbitrarios y no mutaciones. Datos de autenticación se resumen, sin token/stdout auth.

`API(service).dispatch(method,path_with_query,data=None)` → `(status,json)`, prefijo `/api/workspaces/v1`. GET `/workspaces`, POST `/workspaces` body `{name,title,confirmed:true}`. POST `/workspaces/{id}/actions` body `{operation,...args}` mapea operaciones SDK; GET `/workspaces/{id}` devuelve info. El integrador provee su autenticación. CLI `workspace_service.py --parent ALLOWED_PARENT create|list|action|github-read`; action recibe JSON externo/stdin y no shell.

## Inventario de partida (solo lectura)

ADL main inspeccionado, 14 archivos dirty conservados. server.py tiene Workspace browse/select y context-read/scan de solo lectura; seleccionar carpeta no siembra contexto. `src/agent_tools/workspace_read.py` limita lectura a256KiB/250líneas y prohíbe .bago y credenciales, por lo que no se reutiliza como escritor. Hay dos bloques duplicados de GitHub Actions `/api/ci/workflows` y dispatch marcados explícitamente mock (aprox2812/2933); no prueban CI real. Git2.54.0.windows.1 y gh2.92.0 disponibles. `gh auth status` confirma cuenta activa via keyring; no se capturan secretos ni se ejecuta ninguna operación remota. Disponibilidad de auth no equivale a permisos o ejecución de repo/PR/merge.

## Aceptación

Crear solo una raíz nueva; contexto/estado/continuidad presentes; reinicio conserva identidad. CRUD/move/trash/restauración con hash fresco; stale y confirmación incorrecta bloquean. Escape, .git, secretos, links y sobreescritura rechazan. Git stage no consume índice ajeno; commit consume solo selección revisada y falla tras cambiar bytes/HEAD. Rama y diff observables. Planes remotos nunca ejecutados. Google/WhatsApp y UI no forman parte de este módulo. Rutas visuales y capturas de UI se verifican aparte por el integrador.
