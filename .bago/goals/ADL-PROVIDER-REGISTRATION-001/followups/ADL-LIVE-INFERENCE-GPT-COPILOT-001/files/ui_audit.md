# Revisión de proveedores y recorrido de agentes (2026-10-20)

## Contexto y alcance

Repositorio ADL, HEAD `76e57ca7dd5f26fd27a40d81324d945ec798c867`, árbol con cambios previos conservados. La metodología `bago-ui-expert` se adapta al stack real: React 19 + TypeScript + Vite 8, HTTP/WebSocket de FastAPI; las rutas Electron del skill pertenecen a otro producto y no se importan aquí.

Baseline de contenido previo a esta revisión: `%TEMP%/adl-live-providers-20261020-review/baseline.json`, SHA de snapshot `03589730bb4136dc3e90ddc343f51dd44857ba3733edef9a7f10ec02998f28c4`. Alcance parcial declarado: proveedores, rutas de agentes, shell/configuración, Builder/Chat y pruebas relacionadas. No representa evidencia funcional.

## Estructura y navegación

- Entry: `frontend/src/main.tsx`; shell: `App.tsx`; destinos mediante estado React.
- Settings abre un diálogo con Cognition y Proveedores y modelos; cada proveedor tiene un panel hermano.
- `ProviderSettings` usa registro GET/PUT y verificación POST; `AgentBuilder` obtiene proveedores disponibles y guarda el perfil.
- `AgentChat` usa el perfil guardado; `AgentRunner` usa `/ws/agents/run` y conserva el límite de autorización BER.
- Estilos: App/layout y ProviderSettings.css existentes; conservar tema oscuro. Sin nueva dependencia de UI.

## Hallazgos antes de la reparación

| Prioridad | Hallazgo | Corrección prevista |
|---|---|---|
| P0 | `sandbox.run` no es un nombre válido de función en OpenAI; resultados de herramientas sin `tool_call_id` | Adaptar nombres/mensajes en la frontera del proveedor y conservar los IDs |
| P0 | Copilot usa `available_tools=[]` junto a herramienta personalizada y aprobación genérica | Lista explícita de herramientas de propuesta; denegar permisos del SDK; callbacks sin efectos |
| P0 | Tras agotar lecturas, el bucle de chat vuelve directamente a Ollama | Mantener proveedor seleccionado en todos los turnos |
| P1 | Respuestas anteriores pueden marcar una configuración nueva como verificada | Vincular comprobación a revisión del registro y degradar estado al fallar |
| P1 | Sin registro, la UI afirma que GPT/GitHub no están integrados | Exponer soporte de integración incluso sin credenciales |
| P1 | Builder oculta errores/carga del inventario | Estados visibles y reintento |
| P1 | Verificar permite cambios sin guardar y conserva badge anterior al fallar | Bloquear mientras haya cambios y refrescar estado desde servidor |
| P2 | Dos acciones juntas sin separación y aviso amarillo incluso tras éxito | Espaciado responsive y variantes informativa/éxito con el tema existente |

## Plan de cambio y conservación

1. Reparar transporte y estado del proveedor; comprobar adaptadores con transporte simulado claramente identificado.
2. Reparar lectura autorizada y enrutamiento de chat, sin alternar a otro proveedor.
3. Completar estados del formulario y selección proveedor/modelo; usar el propio candidato como propuesta navegable.
4. Probar comportamiento HTTP, rechazo de herramientas ajenas y selección persistida. Preservar Ollama, perfiles antiguos, historial, lectura autorizada y aprobación BER.
5. Compilar, observar interfaz real en navegador y ejecutar generador de README y check exigidos por AGENTS.md.

Ruta: Settings → Proveedores y modelos → OpenAI/GitHub → guardar → comprobar acceso (una inferencia con aviso de uso) → Builder → elegir proveedor/modelo → guardar agente → Chat/Agent Runs. Ruta negativa: credencial rechazada, respuesta vacía, modelo distinto o herramienta no registrada nunca producen estado confirmado ni efectos.

Las pruebas con transporte simulado no prueban acceso externo. El control de acceso en vivo se demuestra solo mediante solicitud explícita del usuario con sus credenciales. No se marca `DEMONSTRABLE` para inferencia externa sin esa observación.
