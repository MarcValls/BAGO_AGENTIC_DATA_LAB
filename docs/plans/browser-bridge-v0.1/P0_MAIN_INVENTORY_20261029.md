# P0 — Inventario de Browser Bridge contrastado con main

**Fecha de corte:** 2026-10-29  
**Repositorio:** `MarcValls/BAGO_AGENTIC_DATA_LAB`  
**Main inspeccionado:** `a9a4929fdbf51dd8872315de25ec8d277902c11c`  
**Git tree raíz:** `c5f8cbe49f79fb1babfdf837fc4fd15ca5f84fb3`  
**Resultado:** `P0_STATIC_INVENTORY_VERIFIED` · `P0_GATE_OPEN`  
**Alcance:** lectura remota del repositorio y de su CI atribuida a ese SHA. No se inspeccionó el Windows local, Chrome instalado ni el worktree activo de Codex.

**Inventario mecanizable con rutas, estados y SHA de blobs:** [P0_MAIN_INVENTORY_20261029.json](./P0_MAIN_INVENTORY_20261029.json). Los SHA son identificadores Git de archivos, no hashes de recibos de ejecución.

## 1. Actualización frente a las bases anteriores

El plan original se preparó en `main@ae8e53e14afa763f816eac9e11ddc0e8a24cdc56`; la revisión documental anterior alcanzó `1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4`. **Ninguna es la nueva base de implementación.**

En el main inspeccionado constan fusionadas:

| PR | Qué incorporó | Alcance real |
| --- | --- | --- |
| #101 | Adaptador de conformidad F-003 y tests | Evaluación de dominio read-only; no autoriza acciones |
| #102 | Previsualización de README y plan de rediseño | Documentación, no nuevo diseño generado de README |
| #100 | Plan Browser Bridge, handoff y revisión contractual inicial | Propuesta y documentación, no host ni extensión |
| #103 | Esquemas P1, 24 vectores, mapa 13 controles y tests | Contratos **candidatos**, no registro/ejecutor operativo |

La PR #103 esté fusionada **no** hace que `browser_native` sea compatible con GEX v1, ni implica que P1 se haya congelado o aceptado formalmente. `P1_GEX_BROWSER_PROFILE.md` y `P1_HANDOFF.md` mantienen el estado de revisión. Sus referencias históricas a PRs abiertas deben interpretarse con las fusiones anteriores, no como estado Git actual.

**Concurrencia observada:** la consulta de PRs abiertas devolvió 0 en el corte; sin embargo, existe la rama remota `work/freelancer-readonly-20261029` (`7b327ca71ce2e3d43299a79473816843b23372f8`) con nuevas rutas en `src/connections/freelancer_readonly.py`, `tests/test_freelancer_readonly.py` y `docs/plans/freelancer-readonly-v0.1/`. No coincide por ruta con los archivos de este inventario, pero toca el área de conexiones que Browser Bridge podría inspeccionar. **El estado de worktrees, archivos locales sin publicar y locks de Codex sigue NO COMPROBADO**. Cero PRs abiertas no equivale a ausencia de trabajo en curso.

## 2. Inventario de capacidades existentes y autoridades

| Frontera | Fuente exacta | Verificado por inspección y límite |
| --- | --- | --- |
| GEX normativo | `docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md`; `GEX_V1_SCHEMA.json` | Contrato v1 `PREPARED / CONTRACT REVIEW REQUIRED`, no FROZEN. `CapabilityRegistrationV1.executor_kind` solo `local` / `mcp`; `GEXRequestV1` exige `agent`. |
| GEX runtime | `src/execution/gex_control.py`; `src/execution/gex_service.py` | Ejecución durable acotada a `fixture.read` sintética. No se observó registro, autorización ni transporte `browser_native`. El perfil de fixture conserva `network=deny`. |
| Autoridad local | `src/execution/gateway.py`; `src/execution/permit/permit_v1.py` | Gateway local con `SandboxRequest` tipada y permisos firmados Ed25519. Ni el gateway histórico ni el permiso aislado demuestran que se puede lanzar Chrome. |
| Ledger | `src/execution/ledger/sqlite_ledger.py` | Propietario de reserva de intento, consumo, `DISPATCH_INTENT`, recibos, replay y reconciliación para GEX. **Reutilizar**, no crear otro ledger. |
| API GEX | `src/api/gex_routes.py`; `src/api/server.py` | Rutas `api/gex` de fixture autenticada. `ws/agents/run` responde `execution_unavailable`; no es un acceso alternativo de ejecución genérica. |
| Conexiones | `src/api/connection_routes.py`; `src/connections/service.py`; `src/connections/transports.py` | Conexiones `docker_mcp`, `mcp`, `http_api`. No confundir stdio MCP con Chrome Native Messaging ni ejecutar Chrome mediante `invoke` genérico. |
| Permisos de proyecto | `src/api/project_permissions_routes.py`; `src/project_permissions.py` | `read_directories` / `write_directories` se aplican a archivos. **No conceden permiso de navegador**. |
| Contexto | `src/context/workspace_binding.py` | Atestación de proyecto, revisión y raíz; no crea autorización. La futura solicitud GEX deberá enlazar el proyecto/instancia exactos. |
| Conformidad | `src/contracts/domain_conformance.py`; `docs/domain-conformance/source/` | Adaptador read-only, `adl.domain_manifest.v1`, 13 controles; mapping de checks **host-owned** y candidato acotado. No valida por sí solo la suficiencia semántica de pruebas específicas de Chrome. |
| Observabilidad | `src/observability/local_trace.py`; `src/observability/chat_inspection.py` | Proyecciones/inspección; no son ejecutores ni fuentes nuevas de autorización. No interpretar una traza como recibo terminal. |
| Investigación web | `src/web_research/core.py` | Lector público HTTPS con autorizaciones y límites propios. **No** lee una pestaña de Chrome ni constituye permiso `activeTab`. |
| Automatización previa | `src/whatsapp/cdp.py`; `src/whatsapp/session.py` | CDP sobre perfil Brave propio y dominio WhatsApp; tiene controles de propiedad/binding e incertidumbre. **Transportes y autoridades distintos** de Chrome Native Messaging. Reutilizar ideas/pruebas de denegación, no tomar el puerto CDP o `Runtime.evaluate` como atajo para el puente. |
| Aplicación | `frontend/src/App.tsx`; `frontend/src/components/AgentChat.tsx`; `GovernedFixtureRunner.tsx`; `ChatInspection.tsx` | Chat general, Settings, runner de fixture e Inspect existentes. Las rutas de UI deberán integrarse sin añadir un orquestador nuevo ni cambiar la identidad de conversación al recibir respuestas asíncronas. |
| Runtime Windows | `scripts/run-local-ui.ps1`; `docs/agent-chat-control/LOCAL_SETUP.md`; `docker-compose.ui.yml` | Host Windows enlaza `127.0.0.1` y selecciona puerto desde 8080, mientras Docker publica 8080 en loopback. **Emparejar instancia y puerto reales**, nunca el primer puerto encontrado. Instalación local y estado vivo no inspeccionados. |

**Alcance de ausencia:** en los árboles comprometidos de `main` revisados no hay carpeta raíz `extensions/` ni `src/browser_bridge/`, `scripts/browser_bridge/` o `src/api/browser_bridge_routes.py`; `tests/contracts/browser_bridge/` sí existe, pero contiene **tests de contratos P1**. Esto no demuestra que el usuario no tenga ejecutables o extensiones fuera del repositorio. No se ha demostrado una lectura real de pestaña con este puente.

## 3. Contrato P1 realmente presente en main

- `P1_BROWSER_SCHEMA.json`: 5 mensajes versionados (`CapabilityProfile`, `BrowserGexRequest`, `SharedTabBinding`, `Dispatch`, `Observation`) con iniciador `HUMAN` o `AGENT` como **contrato futuro**, no API GEX activa.
- `P1_VECTORS.json`: 24 escenarios `SPEC_ONLY_NOT_EXECUTED`; un PASS de sus tests valida expectativas, no una lectura real.
- `P1_CONTROL_MAP.json`: exactamente 13 IDs obligatorios con checks propuestos `bb_*`; estado `PROPOSED_HOST_POLICY_NOT_ACTIVE`. La política `required_checks_by_control` no puede ser autopropuesta por la extensión o el agente.
- `P1_GEX_BROWSER_PROFILE.md`: prohíbe añadir `browser_native` a GEX v1 de forma silenciosa, fabricar agente para la acción humana o abrir otra vía de ejecución.

**Riesgo contractual principal:** falta una extensión tipada y revisada del registro/solicitud que permita `browser_native` y `HUMAN` sin rebajar `fixture.read` ni violar su esquema v1. Hasta aceptarla, la integración P4 permanece `BLOCKED`; P2/P3 solo podrían prepararse en harness aislado y sin acceso a datos reales conforme a los gates P1.

**Reglas no negociables:**

1. La extensión requiere **invocación real del usuario reconocida por Chrome** y un permiso temporal vigente; un mensaje del chat o un registro persistido no crea `activeTab`.
2. ADL/GEX autoriza la misma operación de forma independiente; el permiso Chrome no sustituye al Permit ni el Permit sustituye a Chrome.
3. Un único ledger GEX conserva consumo, `DISPATCH_INTENT` y recibo terminal. La evaluación de conformidad no autoriza operaciones y `teamctl` solo valida evidencias de entrega.
4. Si hubo despacho y falta recibo terminal persistido, el resultado es `UNKNOWN / RECONCILIATION_REQUIRED`, no `SUCCESS`; sin reintentos ciegos. `SUCCEEDED` observado es diferente de `VERIFIED_SUCCESS` independiente.

## 4. Baseline de verificación con identidad de commit

Existe **CI exitosa del propio `main@a9a4929fdbf51dd8872315de25ec8d277902c11c`**:

- [GitHub Actions CI #40843379291](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/actions/runs/40843379291): `SUCCESS`. Incluye suite Python, comprobación README generado, pruebas de frontend/UI/contratos, verificación normativa GEX y build.
- [README consistency #40843379180](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/actions/runs/40843379180): `SUCCESS` en ese mismo SHA.
- [Docker Build #40843379133](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/actions/runs/40843379133): `SUCCESS` en ese mismo SHA.

**Este PASS pertenece al main señalado**: acredita regresión de lo probado por esos workflows, no Windows/Chrome, ni instalación del host, ni Native Messaging ni un recorrido Browser Bridge. La suite de P1 es contractual/sintética.

Regresiones que deberán conservarse antes y después de implementar: 

| Contrato/efecto | Batería existente |
| --- | --- |
| Frontera GEX y recibo terminal | `tests/governed_execution/integration/test_fixture_slice.py` y `tests/api/test_gex_runtime.py` |
| Consumo, replay, persistencia y recuperación | `tests/governed_execution/ledger/test_sqlite_ledger.py` |
| P1 (solo expectativas/esquemas) | `tests/contracts/browser_bridge/test_p1_browser_contracts.py` |
| 13 controles y handoffs | `tests/contracts/evidence/test_domain_conformance.py` y `tests/test_teamctl_integrity.py` |
| Binding de proyecto y permisos | `tests/test_workspace_binding.py` y suites de project permissions |
| Alternativa Brave CDP / WhatsApp | `tests/test_whatsapp_cdp_targets.py`, `tests/test_whatsapp_dom_transport.py` |
| Lectura web ajena al navegador | `tests/test_public_web_read.py` |
| Chat → Inspect y asociación de evidencia | `tests/test_chat_inspection.py` y tests de frontend asociados |
| README generado y UI | `tests/test_dynamic_readme.py`, `tests/test_readme_svg_landing.py`, CI frontend y build |

No se han reejecutado las baterías ni se ha probado una regresión diferencial *desde esta inspección*. La ejecución nueva solo será atribuible a su SHA correspondiente.

## 5. Brechas y decisiones antes de implementar

| ID | Brecha / riesgo | Criterio de cierre | Estado |
| --- | --- | --- | --- |
| P0-01 | Worktree local de Codex, proyecto activo, ramas sucias y scopes de escritura no visibles por GitHub | Registrar identidad de la base local, `git status`, worktrees, misión y reservas de archivos; coordinar `src/connections/` con la rama freelancer | **OPEN** |
| P0-02 | Host, extensión MV3, manifest Native Messaging, HKCU y Chrome real no materializados en el árbol observado | Elegir ubicación de artefactos, identidad de extensión/host, instalación reversible y verificación real Windows | **NOT_RUN** |
| P0-03 | GEX v1 no acepta `browser_native` ni iniciador HUMAN sin agente | Revisión/aceptación del contrato versionado, esquema, registro, política de ejecución y compatibilidad fixture | **BLOCKED P4** |
| P0-04 | Mapping 13 controles → pruebas BB no registrado como política de checks host-owned | Revisar suficiencia semántica, registrar `required_checks`, ejecutar evidencias candidate-bound y evaluación read-only | **PROPOSED** |
| P0-05 | Binding de pestaña por `activeTab` sin evidencia real | Gesto reconocido por Chrome, lectura en fixture propia, revocación/origen/epoch y negativos sin grant | **NOT_RUN** |
| P0-06 | Transporte host ↔ ADL y pairing aún sin implementación | Autenticación fuerte, correlación exacta a instancia/proyecto, límites, nonce/replay, recuperación; no asumir localhost o port 8080 | **NOT_RUN** |
| P0-07 | Incertidumbre de la operación tras `DISPATCH_INTENT` | Test de caída entre despacho y recibo sobre el mismo ledger, retorno incierto y reconciliación, no éxito ni retry automático | **NOT_RUN BRIDGE** |
| P0-08 | Riesgo de colisión con trabajo paralelo en API, UI y conexiones | Acordar scopes exclusivos antes de P2/P3/P4/P5, mantener artefactos aislados y no mezclar con branch freelancer | **OPEN** |

**Mapa de propietario previsto:** GEX conserva identidad, autorización y ledger; el host Windows transporta únicamente órdenes autenticadas; la extensión valida el permiso efectivo de Chrome y extrae texto fijo; Inspect proyecta recibos ya emitidos; conformidad es solo un examen read-only de los checks exigidos por `teamctl`. No hay nueva autoridad ni nuevo ledger en el plan.

## 6. Gate de P0 / continuidad

**REALIZADO Y COMPROBADO:** base actualizada respecto a las PR fusionadas, inventario estático de 34 fuentes por blob, distinción de GEX fixture/P1 especulativo/alternativas, ramas observables, baseline CI del SHA.

**NO COMPROBADO / NO EJECUTADO:** estado del Windows local y Chrome, cambios no publicados por Codex, instalación del host, autorización `activeTab` real, nueva ruta GEX, pruebas de conformidad del navegador, suite en un checkout físico posterior.

**Dictamen:** `P0_STATIC_INVENTORY_VERIFIED`; `P0_GATE_OPEN`. El inventario cumple la actualización documental contra main, **no constituye autorización ni orden para arrancar una implementación**. Antes de programar se debe confirmar la base local y los scopes de trabajo, revisar P1/registry con las autoridades correspondientes, y fijar el baseline Windows/Chrome y la matriz de regresiones.

Para cada nueva fase: comparar `origin/main`, registrar `base SHA` y `candidate SHA`, ejecutar controles y pruebas con sus salidas, conservar los recibos y no modificar `README.md` / `README_DETAILS.md` manualmente. Seguir `AGENTS.md` y el protocolo `teamctl` del repositorio; no inicializar encima de una misión activa ni afirmar que los estados históricos rastreados prueban el estado del worktree actual.

Este inventario es un **snapshot fechado y vinculado a un commit**, no un estado en vivo permanente ni un ledger.
