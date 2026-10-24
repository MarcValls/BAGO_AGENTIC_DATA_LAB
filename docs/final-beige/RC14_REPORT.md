# RC14 · evidencia histórica conservada

## Alcance comprobado

RC14 contiene Configuración destacada en la parte baja de la barra lateral de escritorio y acentos beige rectangulares. Conserva Chat inicial, grupos, localización y foco. La disposición estrecha mantiene su comportamiento adaptable; no se describe una captura estrecha como barra lateral de escritorio.

ZIP: `BAGO_ADL_BEIGE_SETTINGS_20261024_RC14.zip`, SHA-256 `5c8e091df12201ed833f5aabeffa6f5f614a2ce36cf2056b51da99d1e7f7c2ff`. Su inventario contiene492 fuentes públicas y511 archivos de entrega. Las211 fuentes frontend incluidas coinciden exactamente con P, sin extras de fuentes/tests. El [registro de evidencia](RC14_EVIDENCE.json) conserva las identidades de origen y distingue copias de ejecuciones nuevas.

## Resultados del paquete

- Docker frontend del ZIP extraído: **476 PASS**, build PASS.
- Observación visible del preview5193: **24 comprobaciones PASS**, siete PNG nuevas.
- Full nuevo de L: **945 PASS**; su comprobación de README es reproducibilidad, con pruebas NOT_RUN. Este resultado pertenece a L y no reemplaza las941 PASS/1SKIP de P1.
- P mantiene233 archivos protegidos idénticos a P1. No se ha ejecutado otra batería Python completa en este sucesor.

No se suman las32 pruebas focales de BS01 ni se suman ejecuciones de candidatas anteriores. Estas evidencias no acreditan envío WhatsApp, OAuth Google real, invocación de proveedores ni nuevas asignaciones efectivas de herramientas.

## Primera observación y recuperación

La primera observación encontró una raíz vacía y falló su espera; ese intento sigue conservado en L/attempt01. Una recarga normal pasó de cero a un elemento en la raíz, sin recursos fallidos ni errores capturados. La causa permanece **INCONCLUSIVE**. La observación posterior pasó con la aplicación sin cambios. El [diagnóstico](evidence/PREVIEW_DIAGNOSIS.json) y el [registro visual final](evidence/VISUAL.json) se conservan por separado; no se transforma el primer FAIL en PASS.

## Capturas actuales de RC14

Root y el preparador de publicación revisaron las siete imágenes: sin nombres, teléfonos, correos ni QR visibles. Sus máscaras y bytes originales no se modificaron. Son imágenes del preview de RC14; no son prueba de aplicación sobre8093.

| Vista | Imagen |
|---|---|
| Chat, Configuración abajo | [Ver](evidence/visual/01-chat-settings-footer.png) |
| Configuración abierta | [Ver](evidence/visual/02-settings-open.png) |
| Mensajes y acentos | [Ver](evidence/visual/03-mensajes-beige.png) |
| Contactos | [Ver](evidence/visual/04-contactos-beige.png) |
| Barra plegada | [Ver](evidence/visual/05-sidebar-collapsed.png) |
| Contactos estrechos | [Ver](evidence/visual/06-contactos-320.png) |
| Mensajes estrechos | [Ver](evidence/visual/07-mensajes-320.png) |

## Preferencia posterior y estado de publicación

El usuario confirmó después **compactar sólo el bloque de contexto en Configuración**. RC14 se conserva como candidata histórica y no se presenta como resultado final de esa preferencia. El [cambio de alcance propuesto](CR-PFB01-CONTEXT-COMPACTION.json) espera fuentes CL congeladas y paquete RC15. PFB01 permanece abierto; no hay handoff final, stage, commit ni push nuevos. La revisión independiente y la promoción del último alcance siguen pendientes.

Google simplificado y la mejora de legibilidad del contexto sólo pasan a IMPLEMENTED/VERIFIED cuando sus fuentes y pruebas lo acrediten. El catálogo dinámico y la autoridad de herramientas no forman parte de estos cambios visuales. El goal anterior del Inspector continúa pausado.
