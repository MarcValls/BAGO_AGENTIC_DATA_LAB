# Traspaso a Codex — BAGO5_ADL Browser Bridge v0.1

## Actualización P0: main inspeccionado 2026-10-29

**Lee primero:** [P0_MAIN_INVENTORY_20261029.md](./P0_MAIN_INVENTORY_20261029.md) y [snapshot JSON de SHA/blob](./P0_MAIN_INVENTORY_20261029.json). Base inspeccionada: `main@a9a4929fdbf51dd8872315de25ec8d277902c11c`. Es una comprobación remota del repositorio; **NO es una prueba de Chrome, Windows o del worktree local de Codex**.

**Cambio importante desde el handoff histórico:** las PR #100 y #103 **ya fueron fusionadas en main**. P1 se materializó como esquema/contratos/vectores SPEC_ONLY, pero sigue sin activar `browser_native`, sin aceptación/FREEZE acreditado y sin pruebas reales del Browser Bridge. No utilices la base anterior `ae8e53e...` para una nueva implementación.

**Conciliar antes de escribir:** `git fetch origin main`, comprobar identidad del worktree, `git status`, cambios sin publicar, ramas/misiones y scopes ocupados. La rama remota `work/freelancer-readonly-20261029` toca `src/connections/`, área adyacente. No interpretar 0 PRs abiertas como ausencia de trabajo local. El P0 de repositorio está actualizado pero el gate de Windows/worktree permanece **OPEN**.

**Siguientes restricciones:** el registro GEX v1 solo admite `local/mcp` y solicita `agent`; ninguna operación `browser_native` debe pasar por un alias de fixture o por conexiones genéricas. Mantener el único ledger GEX, conformidad read-only, gesto real `activeTab` y estado `UNKNOWN / RECONCILIATION_REQUIRED` sin recibo terminal. P4 sigue bloqueado hasta extensión versionada aceptada y pruebas de integración.

---


## Nota prioritaria para Codex — conformidad y estado pendiente (2026-10-29)

**El puente todavía no está implementado por este plan.** Antes de P1, consulta [DOMAIN_CONFORMANCE_INTEGRATION.md](./DOMAIN_CONFORMANCE_INTEGRATION.md) y contrasta el estado actual de `main`. Se detectó un adaptador de dominio de solo lectura y 13 controles obligatorios integrados tras la base original del plan: `src/contracts/domain_conformance.py` y `docs/domain-conformance/`. La adenda define un **mapeo propuesto** hacia comprobaciones de Browser Bridge, no checks ya creados ni ejecutados.

No llamar a la conformidad para autorizar lecturas, no inventar otro ledger o gateway, no declarar permiso Chrome sin una acción reconocida de usuario en la extensión, no producir SUCCESS si falta un recibo terminal después de despacho. En ese caso se conserva `UNKNOWN / RECONCILIATION_REQUIRED` y se prohíbe el replay ciego.

La nueva adenda no modifica la misión activa, `main`, el runtime ni el estado de verificación. **P0 debe reevaluar concurrencia, base SHA y suficiencia semántica del mapping propuesto** antes de registrar required checks en teamctl. Esta coordinación no implica aprobar la implementación.

---

Fecha: 2026-10-29.
Estado: **PROPUESTO / DOCUMENTACIÓN PARA REVISIÓN**.
Este archivo no es un handoff `DONE` del equipo ni un recibo de ejecución. No modifica el estado de ninguna misión.

## 1. Localización y autoridad

Repositorio: `MarcValls/BAGO_AGENTIC_DATA_LAB`.
Rama documental: `docs/browser-bridge-plan-20261029`.
Documento principal: [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).
Base inspeccionada: `ae8e53e14afa763f816eac9e11ddc0e8a24cdc56` (`main`).
Primer commit que publica el plan: `412bca29af3d530c9cc77eda6b0ec48cd7c01e42`.

La petición del usuario autoriza depositar planes en el repositorio para coordinar trabajo paralelo. **No convierte todas las fases propuestas en una orden de implementación ni autoriza fusionarlas automáticamente en main.**

El plan se prepara para revisión y consumo por Codex. Sus estados no sustituyen la autoridad de `teamctl.py`, la aceptación del usuario ni las comprobaciones reales.

## 2. Instrucción de entrada

Lee `IMPLEMENTATION_PLAN.md` en esta rama y contrástalo con el `origin/main` actual. Conserva la distinción entre lo existente, lo propuesto y lo probado. Identifica conflictos con el trabajo en curso antes de reclamar archivos. No suspendas, reinicies ni sobrescribas una misión activa para acomodar este plan.

El primer trabajo sugerido es **P0: inventario/baseline y mapa de reutilización**. La implementación se abre únicamente con el alcance aceptado y los gates correspondientes.

### Lectura sin cambiar de rama de trabajo

La documentación puede leerse directamente mediante GitHub. En una copia Git autorizada, estos comandos permiten obtener y mostrar la rama sin hacer checkout:

```powershell
git fetch origin docs/browser-bridge-plan-20261029:refs/remotes/origin/docs/browser-bridge-plan-20261029
git show origin/docs/browser-bridge-plan-20261029:docs/plans/browser-bridge-v0.1/IMPLEMENTATION_PLAN.md
git show origin/docs/browser-bridge-plan-20261029:docs/plans/browser-bridge-v0.1/CODEX_HANDOFF.md
```

Los comandos anteriores son instrucciones, **NOT_RUN en el equipo del usuario**. `fetch` actualiza metadatos y referencias Git; coordinarlo con otras operaciones Git en curso. Si falla o el remoto no corresponde al repositorio esperado, detenerse y diagnosticar. No aplicar `--force`, `reset --hard`, `clean`, stash automático ni cambiar la rama del worktree activo como solución.

No es necesario fusionar esta rama para consultar el plan. Para implementar, utilizar otro worktree desde una base remota fresca, respetando `AGENTS.md`; importar solo la documentación necesaria o referenciar su commit. No usar una rama de tarea antigua como base de producto.

## 3. Qué se comprobó y qué no

Se consultó la identidad de `main` y se inspeccionaron archivos/rangos de gateway, GEX, permisos de proyecto, conexiones, documentación UI, Compose y reglas del repositorio. El plan identifica las fuentes exactas y las limitaciones.

Se observó que `GexControl` y el estado de sus rutas están especializados en `fixture.read`, con perfil sintético local. No está acreditado que el registro ya acepte un navegador. La documentación GEX mantiene estado candidato. No extrapolar una capacidad general de ejecución ni degradar la fixture para añadir Chrome.

No se ejecutaron tests, runtime, instalador, Chrome, Windows, generación de README ni `teamctl verify`. No se inspeccionaron cambios locales sin publicar de Codex. La lectura remota no certifica el runtime instalado.

El documento externo `Instrucciones generales de ChatGPT — Perfil de trabajo.md` no se recuperó íntegramente durante esta revisión; no se declara una consulta completa de esa referencia. Se aplicaron las instrucciones visibles del usuario y los archivos del repositorio efectivamente consultados.

## 4. Reglas de concurrencia

Esta rama documental solo añade archivos bajo `docs/plans/browser-bridge-v0.1/`. No modifica código, dependencias, README generados, políticas instaladas ni `.bago/team/runtime/`.

Antes de implementar, inspeccionar `AGENTS.md`, `.bago/team/kit/protocol/TEAM_PROTOCOL.md`, el protocolo de comunicación, la misión elegida y el estado actual. Leer la skill de cada rol asignado. Si existe misión activa, no ejecutar `init` contra su estado. Definir el mecanismo de coordinación admitido por el equipo para una misión distinta; no inventar flags o un store paralelo como autoridad.

Paralelismo sugerido, sujeto a `pair` y contratos aceptados:

- Host/transporte y extensión pueden avanzar por separado después de P1 con contratos compartidos congelados y ámbitos sin solapamiento.
- Integración de gateway/GEX/API y componentes centrales de UI debe reservarse o serializarse cuando otro trabajo de Codex use esos archivos.
- Verificación independiente no se asigna al mismo cambio que implementa el extractor como único oráculo.

No marcar trabajos READY/DONE manualmente en JSON. Todo cierre futuro necesita handoff materializado, comandos reales, resultados y gate terminal del equipo.

## 5. Orden recomendado de implementación

P0 inventario y baseline → P1 contratos/esquemas/vectores → P2 host y P3 extensión → P4 autorización y adaptador durable → P5 chat/UI/Inspect → P6 retest Windows independiente.

P0/P1 preceden a código de producto. P2/P3 pueden usar un harness aislado, claramente etiquetado como desarrollo y sin datos personales; su éxito no demuestra integración ADL. El feature flag permanece apagado hasta los gates de integración.

El primer recorrido de producto es **lectura de una pestaña compartida**, no automatización libre. En Chrome se necesita una concesión de permiso real: el chat por sí solo no activa `activeTab`.

## 6. Restricciones que no deben perderse

Mantener un solo sistema de autoridad. El host y la extensión aplican límites pero no deciden nuevas políticas. No introducir llamadas UI→host que eludan ADL. No heredar autorización de navegador desde permisos READ/WRITE de carpetas.

Emparejar la instancia concreta de ADL, no elegir un puerto arbitrario cuando existan varios frontends. Host en Windows; backend puede estar en Docker. No interpretar localhost ni Origin como autenticación suficiente.

El contenido web es dato no confiable. No ejecutar instrucciones incrustadas en una página, JavaScript arbitrario, comandos de shell ni operaciones sobre cookies/contraseñas. La v0.1 excluye navegación y escritura.

Un recibo faltante tras despacho conserva incertidumbre. No reenviar comandos ciegamente, no fabricar PASS y no convertir un resultado observado en verificación independiente.

Preservar diálogo/composer, permisos por proyecto, agentes/proveedores, Chat/Inspect, GEX fixture y demás capacidades afectadas. Una función nueva que rompa una existente no satisface el cierre.

## 7. Entrega requerida para una fase futura

Cada fase aceptada debe aportar SHA base/candidato, archivos cambiados, contratos y huellas, comandos reales con PASS/FAIL/NOT_RUN, evidencias, riesgos residuales y consumidor siguiente. Los resultados de CI se atribuyen al SHA efectivamente probado.

Antes de publicar, releer main y revalidar divergencias. No atribuir al nuevo candidato resultados de otra rama.

Antes de cierre, cumplir la generación de documentación exigida en `AGENTS.md`:

```text
python scripts/generate_dynamic_readme.py
python scripts/generate_dynamic_readme.py --check --skip-tests
```

Estado en esta entrega: ambos **NOT_RUN**. No editar `README.md` ni `README_DETAILS.md` a mano. Si los checks o gates no pueden ejecutarse, mantener el cambio abierto con el bloqueo exacto. Publicar una propuesta documental no equivale a cerrar una implementación.

## 8. Resumen operativo para el siguiente agente

**Revisar primero, no activar.** El plan está disponible en una rama documental para que pueda consumirse mientras continúa el trabajo actual. No modificar main, contratos congelados ni estado del equipo sin el procedimiento aplicable. La siguiente salida útil es un inventario P0 con conflictos reales y un alcance de implementación acotado; no otro anuncio genérico de que el puente ya existe.
