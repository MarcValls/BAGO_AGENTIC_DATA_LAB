# Gestión visible de agentes

Base obtenida por el orquestador: origin/main c5a78d33fbf5da608f550c4e8809eb6a8cb1be4c.
Checkout aislado agent-management-20261022; no modificar main ni los otros trabajos.

La entrada Agentes del menú muestra la biblioteca real de perfiles guardados:
GET /api/agents/list. Busca por nombre, descripción, ID y tipo; muestra cantidad,
carga, vacío, fallo y actualización. Editar carga GET /api/agents/{id} y reutiliza
AgentBuilder con su PUT existente. Probar tarea abre Agent Runs con ese ID;
Evaluar abre el editor de suite del laboratorio con el mismo ID. Estas acciones
no ejecutan un modelo ni una prueba automáticamente.

Eliminar solicita GET /api/agents/{id}/deletion-review. Devuelve SHA256 de bytes
actuales, nombre e ID, capacidad de eliminar y bloqueos. Después de checkbox
explícito, DELETE /api/agents/{id} recibe confirmed=true y expected_revision.
El servidor toma el mismo agent_lock que el editor y las tareas, revalida bytes,
comprueba todo el historial de jobs, task_runs activos y ledger GEX, guarda
copia exacta en agents/created/.deleted/{id}-{sha}.json y retira el perfil activo.
No borra conversaciones, trazas, tareas, evaluaciones ni jobs. Copia fallida,
estado de actividad ilegible, revisión distinta o trabajo activo impiden borrar.
La copia de recuperación es local, no exporta credenciales ni mensajes.

Alcance de concurrencia: el bloqueo común serializa modificación del perfil y
registro inicial de task_runs. La inspección de jobs/GEX es una observación de
sus almacenes existentes, no una transacción distribuida contra ejecutores
externos. El chat y el laboratorio conservan sus snapshots e historial propios;
no se afirma cancelación de una operación que ya hubiera iniciado.

Todas las mutaciones de aceptación utilizan tmp_path/fixtures aislados. La
demostración de navegador corresponde al orquestador: este trabajo no abre Brave,
no borra perfiles reales y no se integra hasta revisión independiente AM02.
