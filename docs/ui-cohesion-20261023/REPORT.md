# Cohesión visual BAGO — candidata RC9

## Alcance implementado

Una capa canónica `frontend/src/VisualSystem.css`, consumida por un único import desde App. Tres planos compartidos, cabecera principal común, separadores discretos y fondos interiores continuos. Mantiene ángulos rectos y colores semánticos. Las tarjetas de usuario/asistente conservan identidad y acciones propias. No cambia handlers, contratos, permisos ni backend. Los 43 CSS anteriores se conservan con sus hashes; App sólo añade el import.

Se conservan el Inspector ligado a conversación/ejecución, IDs completos, salida «Salir», panel de biblioteca completo, cierre/foco al crear chat, acciones y menú contextual por mensaje y escritura con revisión. «Gestionar agentes» está separado del título y alineado como acción secundaria.

## Identidad

- Candidata: `chat-ui-cohesion-20261023-rc9`.
- ZIP: `evidence/UC02/rc9/BAGO_ADL_UI_COHESION_20261023_RC9.zip`.
- SHA-256: `e6f4b4e864f2f0f97ef72ca894de3e2fc0fe5f455ab98ba03579ace80778f868`.
- Inventario: 505 archivos; 486 fuentes públicas; sin datos ni credenciales.
- CSS: `781408bfb2f1f13f9fcf7df456cecf895ba56f4d7cc945e3c0d56933366d2df9`.
- App: `2310067da95cf83c65872d7d10646c6791cd74ccbb7d8e40f56bc701eaa86e29`.

## Evidencia ejecutada

| Comprobación | Resultado | Alcance |
|---|---|---|
| Focales UC01 | PASS, 126/126 y build | Windows; CSS/identidad/import, conservación y flujos afectados |
| Frontend extraído RC9 | PASS, 457/457 y build | Docker Linux, 50 archivos de pruebas; no sumar a las focales |
| ZIP y extracción | PASS | SHA-256/CRC/inventario, instalación aislada de fuentes |
| Biblioteca completa | PASS | Brave visible; 1920×978 y 320×700 CSS, borrador/modelo preservados |
| Nueva conversación | PASS | Creación real `conv_4911a4f227034445a168800ad863080b`, panel cierra y composer recibe foco; sin envío |
| Mensajes y menú | PASS | Autor, ángulos rectos, acciones dentro de su tarjeta y menú real por botón derecho |
| Inspector | PASS | Conversación vacía del asistente y conversación E1 con IDs conocidos; Salir y foco |
| Idiomas | PASS | Inspector estrecho ES→EN→ES, conversación conservada |
| Familias de pantalla | PASS visual acotado | Nueve vistas actuales y tres suplementos de servicios ya cargados; máscaras de privacidad |

Logs/observaciones: `evidence/UC02/`. La admisión final `ACCEPTANCE.json` y el dictamen independiente UC03 constituyen las puertas; esta tabla no los sustituye. La regeneración README y la aplicación8093 se registran separadamente al terminar, sin atribuir resultados anticipados.

## Hallazgos y correcciones

1. **Piezas superpuestas:** fondos, bordes y degradados repetidos en cada nivel. Se sustituyen por consumidores reales del sistema visual común. Prueba AST de alcance y observación de la cascada final.
2. **Primera focal:**125PASS/1FAIL por exigir que `important` ausente fuera `false`; PostCSS lo devuelve `undefined`. Se corrige únicamente la assertion para seguir rechazando `!important`. Fuentes de producto idénticas; ejecución final126PASS/build. Recibo fallido conservado.
3. **RC8:** preparada antes de esa corrección de prueba; no ejecutada ni aplicada. RC9 contiene los bytes finales y sus propias pruebas.
4. **Observador de controles:** asumía conversación E1 mientras estaba seleccionado el asistente y contaba los botones de fuente como si fueran la X. Corrección del observador, sin cambio de producto; primer código/log/PNG conservados. Ejecución posterior selecciona expresamente ambos propietarios y comprueba IDs. Ver `OBSERVER_CORRECTION.md`.
5. **Capturas:** primeras tomas mostraban estados de carga o máscaras sobre elementos detrás de un diálogo. Se conservan como fases; las tomas de aceptación usan diálogo activo y tres suplementos tras terminar la carga. Las máscaras no son elementos de la UI.

## Conservación y límites

El backend8094 y registro de proveedores continúan por referencia. SDK y efecto previo de escritura se contrastan por hash/mtime; no se repite una escritura para probar estilos. La evidencia de Jaeger de aquella ejecución conserva su alcance histórico; no se presenta como una nueva ejecución del cambio visual.

`agent.run` genérico sigue UNAVAILABLE. No se ejecutó inferencia nueva, envío WhatsApp, experimento Sollutia ni prueba Windows de Docker/Linux. No se validan todas las combinaciones de estados/proveedores ni una matriz responsiva completa. Las descripciones de agentes son datos conservados y pueden estar en otro idioma.

RC7 y misiones anteriores quedan preservadas con sus estados incompletos/supersedidos; no se declara aceptación terminal retroactiva. La revisión independiente UC03 precede a la aplicación8093. Rollback: imagen/montajes RC4 conservados en `../inspect-hierarchy-20261023/evidence/baseline-channel/compose.accepted.json`, manteniendo volúmenes y backend.

## Entrega revisable

`delivery/COHESION.patch` contiene el cambio de esta fase respecto a RC7. El ZIP contiene la composición actual de frontend/backend públicos y el manual. `MANUAL_ES.md` explica uso, instalación y vuelta atrás. La aplicación y salud reales, cuando se ejecuten, quedarán en `delivery/APPLIED.json`.
