# Browser Bridge — actualización diferencial de coordinación

Fecha: 2026-10-29  
Estado: **DOCUMENTACIÓN DIFERENCIAL / P0_GATE_OPEN**  
Rama: `docs/browser-bridge-freelancer-delta-20261029`

## Referencias exactas comparadas

- Snapshot P0 histórico de PR #105: inventario de 34 blobs fijado a `main@a9a4929fdbf51dd8872315de25ec8d277902c11c`, raíz `c5f8cbe49f79fb1babfdf837fc4fd15ca5f84fb3`. El archivo canónico `P0_MAIN_INVENTORY_20261029.md/.json` se conserva sin editar; no se recalculan ni sustituyen sus SHA.
- Revisión de PR #105 disponible en `17ced6e47bc23def3bdb2934e6198444f2249cc2`.
- Candidata Freelancer de PR #104 comparada en `139c79cdda05b838e6efe789230c1a79e316ebc9`; merge base declarado por GitHub: `a9a4929fdbf51dd8872315de25ec8d277902c11c`. El compare de esa base a la candidata informa 2 commits / 20 rutas.
- `main` actual al preparar este delta se compara como 3 commits adelante de la base P0. El compare de `139c79c...` a `main` informa divergencia (3 adelante, 2 detrás), con merge-base `a9a4929...`. Por tanto no se debe presentar la candidata como ancestro idéntico ni dar por probado que ambas puntas son intercambiables.
- PR #104 mantiene la descripción/estado que devuelve GitHub como WIP; los datos de la rama/candidata se tratan por SHA, no como prueba de merge o aprobación.

## Cambio respecto a la fotografía P0

La observación histórica de trabajo paralelo registraba el commit `7b327ca71ce2e3d43299a79473816843b23372f8` y las altas de adaptador, pruebas y documentación. La candidata #104 en `139c79c...` ha ampliado materialmente el área: las 20 rutas incluyen cambios sobre `src/api/connection_routes.py`, `src/api/server.py`, `src/connections/service.py`, `frontend/src/components/AgentChat.tsx`, `ChatTools.tsx` y `ExternalConnections.tsx`; además añade rutas y pruebas específicas Freelancer. Esto amplía la superficie que Browser Bridge deberá inspeccionar. No demuestra conflicto de Git.

La comparación remota de `a9a4929...` con `main` también encuentra cambios en esas superficies compartidas y en documentos Browser Bridge. Dado que los punteros divergen, Codex debe comparar cada blob en su checkout fresco y no resolver solapamientos copiando archivos completos.

## Dependencias y lectura contractual vigente

- **Conexiones/API:** Browser Bridge P0 marcó `connection_routes.py`, `server.py` y `connections/service.py` como superficies de inspección, no como permiso para reutilizar la API genérica. Freelancer ahora demuestra que esos módulos alojan configuración, autorización de lectura y rutas nativas por cuenta. Deben reservarse conjuntamente.
- **Servicio/recibos/privacidad:** el plan Freelancer declara que el flujo candidato emite evidencia de lectura y que no debe conservar cuerpos privados por defecto. El flujo genérico de conexiones tiene recibos que pueden incluir resultados. Antes de compartir un almacenamiento o helper, comprobar ruta efectiva, minimización, retención, fallo de persistencia y separación de datos.
- **Autoridad de ejecución:** el handoff de Freelancer describe un reto local de un uso para la integración candidata, pero declara NO_GO para producción y que no despacha un permiso/efecto tipado por GEX ni usa el ledger GEX. Browser Bridge requiere autorización ADL/GEX independiente de `activeTab`, un único ledger y resultado `UNKNOWN / RECONCILIATION_REQUIRED` cuando falta recibo terminal tras `DISPATCH_INTENT`. No unificar ambos flujos suponiendo compatibilidad.
- **GEX/P1:** el contrato vigente observado en la base P0 conserva `executor_kind: local/mcp`, `GEXRequestV1.agent` obligatorio y ejecución runtime `fixture.read`. Los contratos Browser Bridge P1 siguen siendo SPEC_ONLY. No añadir `browser_native`, fabricar un agente ni convertir el reto Freelancer en autorización GEX. Antes de P4, resolver una extensión versionada y aceptada conservando la fixture.
- **Chat:** las adiciones de Freelancer amplían los componentes compartidos. Las nuevas acciones Browser Bridge deberán evitar colisión de estado, callbacks asíncronos o submission del composer; no cambiar agente/proyecto/conversación al completar una respuesta y mantener contenido de páginas como dato no confiable.
- **Conformidad:** los 13 controles y la evaluación read-only siguen siendo checks de candidata, no autorización ni puerta de ejecución. No crear otro ledger ni otro sistema de conformidad.

## Reservas obligatorias antes de cambios

1. Registrar en la misión efectiva de `teamctl` los scopes concretos y coordinados. Reservar en conjunto `src/api/connection_routes.py`, `src/api/server.py`, `src/connections/service.py`, `frontend/src/components/AgentChat.tsx`, `ChatTools.tsx`, `ExternalConnections.tsx`. No iniciar con una misión activa distinta ni sobrescribir runtime.
2. El propietario de Freelancer confirma el límite de integración/commit y coordina antes de editar cualquier archivo compartido. Si no hay confirmación observable, Browser Bridge puede trabajar en contratos/harness aislado, pero esos archivos compartidos quedan **RESERVED / NOT_EDITABLE**.
3. Obtener checkout Windows limpio; capturar `git status`, `git worktree list`, branch, HEAD, diff y scopes. Comparar `origin/main`, #104 y el worktree local por blob/ruta. Proteger cambios sin publicar.
4. Antes de modificar una API, dibujar explícitamente el contrato de entrada, principal autenticado, binding proyecto/conversación, autorización, idempotencia, persistencia y forma de error/recibo. No añadir otra ruta de ejecución genérica ni duplicar autorización.
5. Antes de tocar chat, comparar los componentes completos y pruebas vigentes en ambos heads; agregar el diseño de interacción Browser Bridge sin reemplazar ni duplicar la UI Freelancer, y fijar ownership de estados/callbacks.
6. Registrar baseline y regresión sobre checkout completo. Los checks de GitHub Actions CI, README consistency y Docker Build atribuidos a ambas PR se consideran únicamente evidencia CI de sus respectivos commits; no prueban Chrome, Windows ni trabajo local.

## PASS / FAIL / NOT_RUN

- **PASS — estático remoto:** commit base P0 identificado; candidatos exactos identificados; compare #104 = 2 commits / 20 rutas; divergencia entre candidato #104 y main actual constatada; rutas compartidas y nuevas dependencias documentadas.
- **PASS — preservación del histórico:** este delta no edita `P0_MAIN_INVENTORY_20261029.md` ni `.json`; mantiene la referencia `a9a4929...` y sus 34 blob SHA.
- **PASS — GitHub según las fuentes de las PR:** CI, README consistency y Docker Build se reportan correctos para #104/#105. Alcance limitado a los workflows y SHAs de esas ejecuciones.
- **FAIL — habilitar integración conjunta ahora:** no aceptable; la rama Freelancer declara NO_GO para producción y no acredita el contrato de autorización/ledger GEX exigido por Browser Bridge. Esto es un bloqueo de diseño/alcance, no un conflicto Git probado.
- **NOT_RUN — worktree y coordinación Windows:** estado Git/worktrees, misión efectiva y scopes locales; acceso a Chrome/Native Messaging.
- **NOT_RUN — runtime y regresión:** ejecución focalizada o suite completa en candidato Windows; pruebas de GEX/ledger, permisos, conexión/recibos, chat renderizado, revocación, caída tras dispatch y lectura real de pestaña fixture.
- **NOT_RUN — inspección independiente y aceptación:** revisión del contrato versionado, mapping 13 controles host-owned y cualquier aceptación/FREEZE formal.

**Decisión:** mantener `P0_STATIC_INVENTORY_VERIFIED / P0_GATE_OPEN`. Este delta actualiza coordinación y reservas; no autoriza P2/P3/P4/P5, no activa Chrome y no cambia el estado de ninguna misión o PR activa.

## Traspaso para Codex

Leer este documento junto a `P0_MAIN_INVENTORY_20261029.md/.json`, `IMPLEMENTATION_PLAN.md`, `CODEX_HANDOFF.md`, `P1_GEX_BROWSER_PROFILE.md` y los contratos GEX vigentes. Confirmar en la rama de trabajo los SHAs anteriores y la punta actual. No editar rutas compartidas hasta superar las reservas 1–3. Mantener evidencia de cada comparación y distinguir **PROPUESTO**, **IMPLEMENTADO**, **VERIFICADO** y **NOT_RUN**.
