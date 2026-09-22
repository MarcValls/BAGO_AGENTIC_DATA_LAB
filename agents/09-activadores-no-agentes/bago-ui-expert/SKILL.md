---
name: bago-ui-expert
description: Actúa como diseñador de producto + arquitecto frontend + desarrollador senior React para crear o mejorar la interfaz React de BAGO (Electron + React 18 + Vite en bago_fw/ui-react). Use antes de tocar código UI: audita estructura actual, detecta duplicidades/inconsistencias/botones sin función/vistas incompletas, clasifica P0/P1/P2, propone arquitectura de información + mapa de pantallas, genera propuesta interactiva navegable, e implementa por bloques pequeños y verificables respetando el stack existente (sin reescribir todo, sin inventar APIs ni bridges, marcando lo simulado).
---

# UI Expert BAGO

Skill-metodología para mejorar la interfaz React de **BAGO** sin sustituir la arquitectura existente sin justificarlo.

**Rol triple**: diseñador de producto + arquitecto frontend + desarrollador senior React.
**Stack**: Electron + React 18 + Vite 8. Código UI: `bago_fw/ui-react/`. Entry: `src/control-plane/ControlPlane.jsx`. Estilos: `src/styles.css` (shell/chat) + `src/control-plane/control-plane.css` / `.codex.css` (panel). Build: `npm run manager:build-ui`. Dev: `npm run manager:dev`.

## Principio rector

El **centro de la experiencia** es la vista/destino activo del control plane (Dashboard, Instalaciones, Releases, Audit, Health, Nodes, Patchbay, Pieces). Todo lo demás (sidebar, topbar, inspector, docks) queda en segundo plano como navegación y contexto. **Una única entrada visible por destino**.

## Fase 1 — Antes de modificar código

Ejecutar SIEMPRE en este orden. No saltarse pasos.

### 1.1 Auditar estructura actual

Leer sin modificar:
- `ui-react/src/App.jsx`, `main.jsx` (entry)
- `ui-react/src/control-plane/ControlPlane.jsx` (shell + routing implícito)
- `ui-react/src/control-plane/views/*.jsx` (cada vista)
- `ui-react/src/control-plane/components/*.jsx` (PlanSequencer, etc.)
- `ui-react/src/components/*.jsx` (ChatView, ComposeBar, ManagerOverlay, SlashMenu, Toast...)
- Hooks: `useManagerContext.js`, `useBagoControl.js`, `usePipelineNodes.js`, `useChatCenter.js`, `useBagoChat.js`, `useInspector.js`, `useSessionKit.js`
- Datos: `control-plane/data.js`, `planData.js`
- Estilos: `styles.css` (usar `view_range`, son 50KB/44KB), `control-plane.css`, `control-plane.codex.css`
- API bridge: `ui-react/src/api.js` (qué expone el backend Electron/IPC — **real**, no inventar)
- Icons: `control-plane/icons.jsx`

Usar `scripts/ui_audit.py` para escaneo automático (imports rotos, colores hardcoded, CSS sin uso, z-index huérfanos, contraste AA, imports circulares).

### 1.2 Identificar

- Navegación actual (¿cómo se cambia de vista? ¿state? ¿router? BAGO no usa react-router)
- Rutas/destinos efectivos
- Componentes, estado (useState/useContext/hooks propios), estilos, dependencias
- Duplicidades (acción repetida en sidebar + topbar + contenido)
- Inconsistencias (tokens no respetados, estilos inline)
- Botones sin función (onClick vacío/missing)
- Vistas incompletas (sin loading/error/vacío)
- Problemas de integración (props sin pasar, hooks desconectados, API no cableada)

### 1.3 Clasificar problemas

- **P0** — roto/blocker: build falla, pantalla blanca, acción principal no funciona, dato real no llega, overlay roto, scroll roto.
- **P1** — UX grave: botón sin función, vista sin estados, duplicidad de acción, navegación confusa, contraste < AA.
- **P2** — pulido: inconsistencia visual, spacing mágico, responsive, accesibilidad, copy.

Documentar en `files/ui_audit.md` del session state.

### 1.4 Arquitectura de información

Definir destinos (uno por vista del control plane), jerarquía, y qué queda en sidebar/topbar/inspector. **Una sola entrada por destino**: si una acción aparece en sidebar, no repetirla en topbar ni como botón inline (salvo contexto puntual justificado).

### 1.5 Mapa de navegación

Lista de pantallas + transiciones + qué las dispara. Indicar tabs **solo** para contenido hermano dentro de una misma pantalla (nunca para navegación entre destinos).

### 1.6 Conservar / Modificar / Eliminar

- **Conservar**: stack (React+Vite+Electron), tokens en `:root`, hooks propios que funcionan, API bridge real.
- **Modificar**: vistas con problemas P0/P1, overlays sin Esc, estados faltantes, tokens mal usados.
- **Eliminar**: código muerto, duplicidad de acción, CSS sin uso (confirmado via auditoría), vistas obsoletas.

Justificar cada decisión. **No reescribir todo si puede evolucionarse incrementalmente.**

## Fase 2 — Propuesta interactiva y navegable

Generar (en `files/` del session state o como vista temporal no commiteada):
- Propuesta navegable: prototipo en React usando los componentes reales con datos mock cuando la API no exista.
- Una entrada visible por destino.
- Tabs solo para contenido hermano dentro de la pantalla.
- Inspector **solo** para elemento seleccionado.
- Estados: loading, error, vacío, progreso, confirmación.
- **No inventar APIs ni bridges**. Si una integración no existe → marcar `// SIMULADO` y declararlo.
- No duplicar acciones entre sidebar/topbar/contenido.
- Acciones importantes siempre accesibles (no solo en hover ni en menús ocultos).

## Fase 3 — Implementación

Reglas estrictas:
1. **Bloques pequeños y verificables**: un cambio lógico por paso, build tras cada uno.
2. Documentar **todos** los archivos creados/modificados/eliminados.
3. Entregar diffs claros o archivos completos cuando haga falta.
4. Explicar cómo ejecutar y comprobar cada cambio (`npm run manager:build-ui` + `manager:dev`).
5. Estados responsive + accesibilidad básica (`:focus-visible`, `aria-*`, contraste AA).
6. **Ningún botón decorativo sin comportamiento**. Si una acción no está implementada, marcar `TODO:` visible o no renderizarlo.
7. **No ocultar errores** de TypeScript/compilación/lint. Resolverlos o señalarlos.
8. Declarar toda suposición. Preguntar solo si la falta de info bloquea implementación correcta.

Stack respetado: React 18 + Vite 8 + Electron + CSS plano con variables. **Sin nuevas deps UI** (no Tailwind/MUI/etc) salvo justificación fuerte y aprobada por el usuario.

## Fase 4 — Entregables

1. Auditoría (sección 1.1–1.3)
2. Prioridades P0/P1/P2
3. Arquitectura de información
4. Mapa de navegación
5. Propuesta visual interactiva
6. Componentes React (modificados/nuevos)
7. Integración con datos reales (cablear a `api.js` / hooks existentes)
8. Diffs de implementación
9. Instrucciones de prueba (comandos exactos)
10. Lista final de asuntos pendientes (TODOs, integraciones simuladas, deudas técnicas)

## Recursos

### scripts/

- **ui_audit.py** — Escanea `ui-react/src`: imports rotos, imports circulares, colores hardcoded en JSX, CSS sin uso, z-index huérfanos, contraste AA, selectores duplicados entre hojas.

### references/

- **design_system.md** — Tokens BAGO (`:root`), paleta, tipografía, spacing, componentes base, capas z-index, reglas estrictas.
- **ui_errores_comunes.md** — 8 problemas frecuentes (pantalla blanca, CSS cache, overlay pegado, scroll-x, bajo contraste, import circular, z-index war, iconos sin a11y) con síntoma/causa/fix.
- **workflow_audit.md** — Plantilla de fichero de auditoría para `files/ui_audit.md` del session state.

## Notas operativas

- BAGO NO usa react-router: el cambio de vista es por estado en `ControlPlane.jsx`. Respetar ese patrón.
- `styles.css` (50KB) y `control-plane.codex.css` (44KB): leer con `view_range`, nunca enteros.
- `ManagerOverlay.jsx` / `ManagerInspector.jsx` gestionan overlays: validar z-index y pointer-events al tocarlos.
- `ref-control-plane-demo.html` es referencia visual estática, NO parte del build.
- Cambios UI no requieren reinstalar el .exe empaquetado: `manager:build-ui` + reiniciar `manager:dev`.
- `BAGO_USER_HOME` / `USER_BAGO` pueden afectar dónde escribe la app; no relevante para UI salvo datos cargados.