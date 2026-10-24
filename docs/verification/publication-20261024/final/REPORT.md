# BAGO · sucesor de publicación

## Identidad y alcance

Este sucesor parte del commit local `165d01588bf86944d99dd5c8d9c632fa2736dc29`, preparado sin publicación remota. Añade únicamente el orden de requisitos de CI, once reglas explícitas de conservación de bytes y la navegación visual congelada en HR01. La candidata final y sus evidencias se identifican en el inventario final de esta carpeta.

La operación prepara una revisión de GitHub. No declara validado todo el sistema, ejecutada la CI alojada, concedidos nuevos permisos ni conectados proveedores.

## Cambios

- CI: los dos pasos existentes de Node y `npm ci` se trasladan antes de pytest. Se conservan los 32 pasos y sus contenidos, permisos y acciones.
- `.gitattributes`: once rutas concretas con `-text` conservan los bytes que verifican contratos históricos de SHA. No se altera la política global del repositorio.
- Navegación: Configuración → Espacio de trabajo → Chat → Agentes → Capacidades → Comunicaciones → Inspector. El CSS nuevo está en `NavigationOrder.css`; `App.css` conserva exactamente RC10. Chat continúa como pantalla inicial.

Consulta el [manual de navegación](AUTHORITY_ORDER/MANUAL_ES.md) y el [plan de capacidades, PROPOSED](AUTHORITY_ORDER/authority-design/CAPABILITIES_PLAN.md). El plan no implementa un registro dinámico ni admite asignaciones efectivas de herramientas.

## Evidencia y continuidad

El [cambio explícito](CHANGE_REQUEST.json) conserva hashes anteriores y nuevos. PP01 y PP02 son historia de P1: sus fuentes e inventarios no se reescriben para aparentar una nueva validación. Su runtime cerrado está archivado localmente; el [baseline](P1_SOURCE_BASELINE.json) registra sus identidades.

La batería Python de P1 produjo **941 PASS y 1 SKIP**, ejecución `45204dcac9b246ee82ecbdd9d6684622`. Se hereda exclusivamente después de comprobar que todos los archivos Python de `src`, `tests`, `scripts`, los requisitos y los inputs del README conservan sus bytes. No se ejecuta otra batería completa en este sucesor. El [control de fuentes y CI](CONTROLS_CHECK.json) separa esta herencia de la comprobación nueva.

La [admisión RC13](RC13_ADMISSION.json) relaciona **476 pruebas frontend PASS y build PASS** con las **211 fuentes frontend idénticas** del paquete `BAGO_ADL_NAVIGATION_20261024_RC13.zip`, SHA-256 `32f9b1b860a308c2341afbdb9ba83898ba37fab85c8fba90f88738f3cf3c58fe`. Es evidencia heredada de esa ejecución del paquete; no otra batería ejecutada en P. La observación del preview registró **22 comprobaciones PASS**, sin guardados, envíos ni inferencias. Una ayuda de CLI o el estado de una misión no sustituye esa prueba. Las comprobaciones finales y el README reproducible se documentan en el recibo de PF01; PF02 realiza la revisión independiente.

## Capturas actuales RC13

Estas siete imágenes conservan sus bytes originales y sus máscaras de privacidad. Fueron revisadas visualmente; no muestran nombres, teléfonos, correos ni QR. Corresponden al preview5193 de RC13, sin atribuir una aplicación a8093.

| Vista | Captura |
|---|---|
| Chat y orden lateral | [Ver](visual/01-menu-chat.png) |
| Configuración | [Ver](visual/02-settings.png) |
| Mensajes | [Ver](visual/03-mensajes.png) |
| Contactos | [Ver](visual/04-contactos.png) |
| Navegación estrecha | [Ver](visual/05-menu-320.png) |
| Mensajes estrechos | [Ver](visual/06-mensajes-320.png) |
| Contactos estrechos | [Ver](visual/07-contactos-320.png) |

## Límites y pendientes

- CI alojada y publicación remota: **NOT_RUN** en PF01.
- WhatsApp real, QR, envío de mensajes, proveedores y efectos sobre clientes: **NOT_RUN** en este sucesor.
- Catálogo de seis capacidades, cinco IDs configurables heredados y herramientas reales del chat siguen siendo inventarios distintos. La asignación efectiva requiere su propia admisión de extremo a extremo.
- La referencia de fuentes del catálogo necesita resolver la identidad del paquete en vez de la raíz del workspace del usuario.
- Historial por entidad y autoridad funcional nueva: **PROPOSED**. El nuevo orden visual conserva los permisos existentes.
- El goal anterior del Inspector continúa pausado.
- Los avisos de espacios/saltos de línea de P1 se conservan como deuda menor; no se reformatea producto ni se modifican manifiestos históricos.

La integridad del working tree, la identidad del índice Git y una ejecución de CI alojada son evidencias diferentes. Root registra el índice y la base remota final antes de publicar. No se suman pruebas focales, reejecuciones ni pruebas heredadas para inflar conteos.
