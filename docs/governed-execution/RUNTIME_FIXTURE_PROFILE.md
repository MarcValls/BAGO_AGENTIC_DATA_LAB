# Perfil local GEX: propuesta, aprobación y recibo

Estado del perfil: **VERIFIED para una lectura sintética inmutable con aprobación autenticada**. La revisión independiente W11 completó en pantalla una propuesta real de `ollama-cloud/gemma4:31b`, aprobación exacta, permiso firmado de un uso, ejecución, observador y recibo durable verificado. Tras reiniciar el servicio recuperó el mismo recibo y rechazó repetir la ejecución sin un segundo envío. También comprobó la recuperación en la instancia abierta por `INICIAR_APP.cmd`. El gate y las identidades exactas viven en `.bago/goals/adl-seven-verticals-20261020/spiral-gex-integration/`, especialmente `evidence/W11_VERIFICATION.md`; los artefactos públicos, en `output/playwright/gex-runtime-20261020/`. Esta comprobación no cierra las siete verticales, la CI del candidato ni la ejecución de herramientas genéricas.

Este perfil conecta una tarea de un agente guardado con una propuesta de su proveedor/modelo, una aprobación autenticada ligada a la solicitud completa, un permiso Ed25519 de un uso, una reserva transaccional SQLite, el gateway y sandbox tipados, una lectura de fixture y un recibo durable comprobado por un observador independiente. El dato es sintético e inmutable: `adl.synthetic.customer-summary.v1`. El proveedor de inferencia puede ser un servicio real; el ejecutor de fixture devuelve bytes locales publicados y no accede a servicios externos.

## Autoridad y alcance

- El operador provisiona una credencial limitada al agente y al workspace desde una herramienta local. La API no registra identidades ni acepta un principal/workspace declarado por el cliente o modelo.
- El modelo recibe exclusivamente el esquema `fixture.read`. Su respuesta propone; el backend crea y valida el sobre GEX completo, su digest y la decisión `REQUIRE_HUMAN`.
- La pantalla muestra los argumentos, el alcance, las restricciones, la política, el workspace, el digest y la caducidad antes de aprobar. La sesión del operador autentica la decisión; el servidor firma aprobación y permiso y verifica sus enlaces antes de consumirlo.
- SQLite reserva el permiso y `DISPATCH_INTENT` antes del gateway. Los recibos y los resultados normativos enlazan solicitud, decisión, aprobación, permiso, intento, observador, límites efectivos y hashes de salida.
- Un solo proceso posee el estado mediante un bloqueo del SO. Un reinicio recupera registros; nunca reejecuta automáticamente un intento incierto. La ausencia de recibo tras un intento exige reconciliación.
- El estado, las bases y la clave de firma residen fuera del workspace autorizado. El perfil local protege archivos del usuario; no promete resistencia frente a un administrador del host, HA, sandbox de SO ni identidad externa corporativa.
- `agent.run`, `/ws/agents/run`, `mcp.execute` y `sandbox.execute` genéricos permanecen `UNAVAILABLE / FAIL_CLOSED`. Este perfil no habilita escrituras, procesos, shell, red de herramientas ni rutas arbitrarias.

`GET /api/gex/status` informa configuración y disponibilidad del control local. `READY` no significa que el proveedor haya respondido ni que una tarea se haya ejecutado. La ejecución solo se representa como verificada con recibo y resultado persistidos, firmas, cadena y postcondición comprobados.

## Preparación y arranque

1. Configurar un proveedor y guardar un agente con modelo explícito desde ADL. La autorización del fixture procede del registro y de la credencial limitada del operador, independientemente de la lista histórica de herramientas del agente.
2. Preparar un repositorio Git sintético separado con un commit inicial. Elegir un directorio de estado absoluto, fuera de ese repositorio. En desarrollo, usar ubicaciones ignoradas y excluir las credenciales de cualquier exportación pública.
3. Desde la raíz, provisionar una sola vez:

```powershell
python scripts/provision_gex_fixture.py --state-dir <estado-absoluto> --workspace <workspace-absoluto> --principal principal_demo --agent-id <id-guardado>
```

La salida contiene una clave secreta de operador, mostrada una sola vez. Conservarla en un almacén privado; excluirla de logs, capturas, repositorios y evidencias. Repetir la provisión sobre el mismo estado produce conflicto y conserva las claves y registros existentes.

4. Configurar ese estado para el proceso y ejecutar el launcher de la raíz:

```powershell
$env:BAGO_GEX_STATE_DIR = '<estado-absoluto>'
$env:BAGO_GEX_WORKSPACE_ROOT = '<workspace-absoluto>'
.\INICIAR_APP.cmd
```

El launcher compila la UI, reinicia únicamente la instancia que administra para este checkout y abre su puerto local libre. Mantener las mismas variables al reiniciar para recuperar el mismo estado. La configuración incompleta, una clave ausente, un workspace distinto o un segundo propietario dejan el perfil sin disponibilidad.

## Recorrido en pantalla

En **Agent Runs**, introducir el ID autorizado y la clave de operador para crear una sesión. Pedir una lectura del fixture sintético. Revisar la propuesta completa y pulsar **Aprobar solicitud exacta y ejecutar ahora**, **Rechazar** o **Cancelar solicitud**. Una propuesta desconocida o inválida conserva evidencia de denegación y no obtiene una solicitud/permiso de ejecución.

El resultado muestra el recibo, los IDs enlazados, la aprobación y el permiso firmados, los hashes del ejecutor y del observador y la traza durable. El JSON completo incluye los artefactos normativos `gex_receipt` y `gex_verification`. Un recibo ausente, alterado o no comprobado se presenta como no verificado. Ante una espera incierta, recuperar el registro por su ID antes de decidir otra vez.

Tras recargar la pantalla o reiniciar el proceso, autenticar una nueva sesión del mismo operador/agente y usar **Recargar estado durable** con el ID anterior. La recuperación no llama al proveedor ni ejecuta la herramienta. Una aprobación repetida no vuelve a consumir el permiso y deja evidencia de replay. Los tokens permanecen en memoria de la vista y no se guardan en URL ni almacenamiento del navegador.

## API y pruebas

La fábrica de router se conecta al cargador real de agentes guardados y al resolvedor real de proveedores en `src/api/server.py`. Las rutas de sesión, propuesta, decisión y recuperación están en `src/api/gex_routes.py`; el control y las fronteras tipadas, en `src/execution/`. `scripts/provision_gex_fixture.py` es una operación local del operador, no un endpoint de bootstrap.

Los tests de `tests/api/test_gex_runtime.py` usan HTTP, SQLite, firma, CAS, gateway y observador reales con un callback de proveedor **simulado** para controlar los casos adversos. Las pruebas de UI usan respuestas HTTP simuladas. La evidencia de proveedor y navegador reales pertenece al gate independiente W11 y debe citar el candidato y servidor exactos.

Los documentos normativos, esquema, máquina de estados, vectores y referencia JCS se importan de `ac41edb0eead19caf128cf83cd99a8481ed8db95` con los hashes de su revisión independiente W25. [SOURCE_FREEZE_20261018.md](SOURCE_FREEZE_20261018.md) conserva esa decisión histórica de especificación; no es una validación del runtime de este checkout. El contrato histórico `CRIT_ADL_GOVERNED_EXECUTION_001.md` registra las brechas de su base anterior. El gate actual debe demostrar las garantías nuevas para este perfil concreto y mantener el cierre de la ejecución genérica.
