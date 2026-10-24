# Acción Gestionar agentes integrada en la cabecera

Orden explícita posterior: el botón Gestionar agentes resulta un pegote en su ubicación actual. Ajuste visual del acceso existente, no nueva capacidad ni ruta.

Delegado /root/failed_chat_ui bajo integración FS02: sólo AgentChat.css append a partir de prefijo9876ba72e23fc88a87935c61e1a4fadec33458ee1909aafe22f0e5aa42d040ad, nuevo frontend/tests/ui/chat-shell/manage-action.test.tsx y manage-action/**. TSX87582b31ffbf297b76667b03ef4c393625a2c08e307ff095c3afc4f026779dd9 y resto de fuentes congeladas intactos.

Cabecera de agentes: título a izquierda, acción discreta a derecha con gap12px y wrap estrecho; botón transparente y borde suave, foco/hover visibles, recto, sin ancho impuesto. Mantener label/función y tamaño usable. No tocar geometría de panel completo ni mensajes, API, permisos o otros estilos. Nuevo before/delta/prueba/build/handoff; el handoff FS01 anterior conserva su identidad.

Root integra en RC7 final, conserva RC6 como fase anterior sin atribuirle este resultado, verifica extracción y frontend y observa el flujo completo antes de revisión independiente y aplicación8093. El registro de pruebas se mantiene por candidato y sin sumar repeticiones.

## Extensión mínima de prueba por fallo demostrado

Primera focal18PASS/1FAIL: regex `content:` en inspector-color.test.tsx confunde la propiedad legítima `justify-content:` con contenido generado. Se autoriza al mismo delegado editar únicamente esa assertion usando el AST PostCSS ya existente: contrastar nombre exacto de declaración `content` (normalizado), conservando la prohibición real y fixtures/whitelist/preservación. Añadir un control de la propiedad real frente a justify-content si procede. No deformar CSS ni debilitar la puerta. Guardar fallo y nuevo hash del test en el handoff.
