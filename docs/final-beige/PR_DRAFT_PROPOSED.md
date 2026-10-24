# BAGO: servicios integrados y navegación revisable

## Estado del borrador

Texto preparado; no se ha publicado. Los acentos beige y Configuración abajo están **PREPARED** en esta candidata, con evidencias RC14 conservadas. El usuario ha confirmado después compactar sólo el bloque de contexto de Configuración. Se espera su implementación congelada y paquete RC15, aceptación independiente y PFB02 antes del cierre. RC14 queda como candidata histórica; no acredita esta última preferencia.

## Cambios propuestos para revisión

- Servicios y pantallas de comunicaciones, contactos, WhatsApp, workspace y revisión de acciones procedentes del snapshot ya auditado.
- Configuración en la parte baja de la barra lateral, destacada, con acentos beige; conservación del estilo rectangular y de los permisos existentes.
- Requisitos Node/npm instalados antes de pytest en CI, conservando los pasos y permisos.
- Once archivos con conservación explícita de bytes por sus contratos históricos de integridad.
- Manuales, límites y capturas nuevas de la candidata final, cuando terminen sus verificaciones.

## Evidencia

| Candidata y entorno | Resultado | Alcance |
|---|---|---|
| P1, Python local | 941 PASS,1SKIP | Herencia condicionada a233 archivos protegidos idénticos; no nueva batería de P |
| RC14, nuevo full de L | 945 PASS | Registro separado de P; no sustituye su conteo |
| RC14, Docker del ZIP extraído | 476 frontend PASS y build PASS | 211 fuentes frontend de P coincidentes |
| RC14, preview visible5193 | 24 comprobaciones PASS,7PNG | Pie de Configuración, beige, navegación/foco/idiomas y vistas estrechas; máscaras de privacidad |
| RC15, último alcance | PENDING | Compactación del bloque de contexto y verificación independiente aún requeridas |
| GitHub CI alojada | NOT_RUN | Se informará sólo tras una ejecución real |

Los [resultados RC14](RC14_REPORT.md) conservan el primer intento de preview fallido y su causa INCONCLUSIVE; la observación posterior pasó con fuentes sin cambios. No se suman pruebas focales ni ejecuciones anteriores. RC13 no acredita los nuevos colores ni la posición final de Configuración. Las métricas RC15 se completarán desde sus registros finales, sin atribuirle resultados de RC14.

## Límites

CI alojada, OAuth Google real, envíos WhatsApp, proveedores y asignación efectiva de nuevas capacidades no se atribuyen a este PR. El flujo Google simplificado y un catálogo dinámico siguen PROPOSED. Se conserva la pausa del goal anterior del Inspector. Se solicita revisión como draft, sin merge automático.
