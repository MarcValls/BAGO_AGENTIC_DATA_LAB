# Workspace integrado — candidata revisable

Base recién obtenida: origin/main `c5a78d33fbf5da608f550c4e8809eb6a8cb1be4c`; branch `codex/workspace-integration-20261023`. Nunca se modifica main para construir esta candidata.

El backend monta `/api/workspaces/v1` sobre los cuatro módulos independientes **sin modificar sus bytes**. `src/workspace_sdk/__init__.py` es solo un cargador de compatibilidad para sus imports puros, con rechazo de colisión de nombres; no incorpora otro motor ni lógica SQL/Git duplicada. API.dispatch y CLI usan el mismo núcleo. Configurar una carpeta padre existente y dedicada mediante BAGO_WORKSPACE_PARENT; si falta, la UI informa indisponible y no adopta el CWD.

La pantalla Workspace contiene WorkspaceManager y conserva CognitionSettings workspaceOnly (carpeta actual, lectura de contexto y memoria). El nuevo gestor no deduce permiso de edición sobre la carpeta actual heredada. «Usar este proyecto en ADL» reutiliza la selección existente solo tras revisión. El contexto/estado/continuidad de proyectos nuevos se leen y editan mediante los tres paths permitidos por el SDK.

El chat consume la propuesta estructurada descrita en [CHAT_CONTRACT.md](CHAT_CONTRACT.md), la conserva en referencias de la conversación y renderiza WorkspaceManager inline. El modelo propone intent/nombre/ruta, sin autorización ni ejecución. La tarjeta queda incompleta cuando falten título/proyecto/archivos. El recorrido de Chat con herramientas de lectura autorizadas conserva su batería específica; la nueva propuesta se prueba en el control semántico normal sin adjuntos. No se atribuye cobertura adicional a combinaciones no probadas.

SDK fuera de BAGO, desde otro CWD:

```powershell
python -B "RUTA_CANDIDATA\src\workspace_sdk\workspace_service.py" --parent "RUTA_PADRE_FICTICIA_EXISTENTE" create --name demo --title "FICTICIO" --confirmed
python -B "RUTA_CANDIDATA\src\workspace_sdk\workspace_service.py" --parent "RUTA_PADRE_FICTICIA_EXISTENTE" list
```

No pip para ese CLI; Git local se requiere al usar sus operaciones. Las fuentes conservadas están ligadas al pack standalone y a sus manifiestos heredados en HANDOFF.json/REUSE_MAP/SYNC_EXTRACTION/AUTH_EXTRACTION. Esas evidencias pertenecen al núcleo y no se presentan como pruebas visuales nuevas de ADL.

Pruebas propias: `python -m pytest tests/test_workspaces_routes.py tests/test_semantic_navigation.py -q`, `npm test --prefix frontend -- tests/workspace/manager.test.tsx`, `npm run build --prefix frontend`. La prueba backend crea repositorios, archivos y commits solo en raíces efímeras; las respuestas del modelo son fixtures, no inferencia remota. Los tests de interfaz son DOM simulado, no captura Brave. HOST_DEMO.md (pendiente: no se incluye una demostración de host en esta entrega) define la reproducción visual pendiente.

Los cambios son preparados para revisión. La misión propia está fuera del KIT en mission.json; el runtime heredado de este checkout se conserva en historical-team-runtime y no forma parte del patch de producto. WS02 exige revisión independiente y host visual; no se declara misión completamente cerrada desde esta implementación.

Sin cambios en proveedores, cuentas, registros globales, keyring ni instalaciones. Pillow 12.2 para ejecutar las pruebas existentes del generador README se instaló únicamente en test-deps dentro de este checkout; no forma parte del producto ni del patch.
