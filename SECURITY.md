# Política de seguridad

## Estado y alcance

BAGO Agentic Data Lab (ADL) es software experimental. Esta política cubre el
código y las integraciones mantenidas en este repositorio. No declara una
auditoría completa, una certificación ni la ausencia de vulnerabilidades.

| Línea o distribución | Situación de seguridad |
| --- | --- |
| Rama `main` | Desarrollo activo; sin garantía de estabilidad ni plazo de corrección. |
| Candidatas de integración, RC y snapshots | Experimentales. Identificar sus bytes y entorno antes de atribuirles una prueba. |
| Versiones anteriores o instalaciones modificadas | Sin compromiso de mantenimiento o backport declarado. Reproducir contra una candidata identificada cuando sea posible. |
| SDK y proveedores externos | Se aplica también la política de su proyecto de origen; su inclusión no amplía el soporte de ADL. |

Un test local o un hash correcto no demuestra seguridad global ni funcionamiento
con servicios reales. La integración de Contactos, Comunicaciones, WhatsApp y
Workspace tiene pruebas locales con datos aislados; el acceso vivo a Google,
una sesión WhatsApp concreta, los proveedores y cada instalación requieren su
propia comprobación. Una propuesta del chat no constituye autorización para actuar.

## Comunicar una vulnerabilidad

**No publique credenciales, datos personales, perfiles de navegador, conversaciones,
adjuntos privados, pruebas de explotación ni detalles que faciliten un ataque en
issues, pull requests, capturas o logs públicos.**

En la comprobación del **23 de octubre de 2026**, la API de GitHub indicó
`enabled: false` para el reporte privado de vulnerabilidades de este repositorio.
La [página de seguridad](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/security/policy)
puede cambiar después de esa comprobación. Este documento no habilita ese servicio
ni establece un correo privado alternativo.

1. Si GitHub muestra **Report a vulnerability / Informar de una vulnerabilidad**
   como opción privada en la sección Security del repositorio, utilice esa opción
   y compruebe que el formulario es privado antes de aportar detalles.
2. Mientras no exista un canal privado disponible, solicítelo al mantenedor
   mediante una [issue del repositorio](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/issues)
   con un mensaje neutro, por ejemplo: «Necesito un canal privado para comunicar
   una posible vulnerabilidad». Incluya sólo esa solicitud, sin describir el fallo,
   los sistemas afectados, su explotación ni adjuntar evidencias sensibles.
3. Espere la indicación de un canal privado verificable antes de remitir el
   informe técnico. Si no recibe una vía adecuada, conserve el informe de forma
   privada; no interprete el silencio como autorización para divulgarlo.

No hay un plazo de respuesta, SLA, recompensa ni programa de bug bounty declarado.
La existencia de esta política tampoco confirma que haya un equipo de respuesta
permanente. Para un incidente activo, deje de utilizar la capacidad afectada y
aplique la respuesta de su propia organización; no espere a una respuesta del repo
para revocar una credencial comprometida por los medios de su proveedor.

### Informe técnico mínimo, una vez disponible el canal privado

- Componente, commit o candidata, SHA-256 si corresponde, sistema operativo y
  versiones de dependencias relevantes. Distinga fuente, paquete e instalación.
- Resultado esperado y observado; impacto y condiciones necesarias para producirlo.
- Pasos mínimos con datos ficticios y cuentas propias de prueba. No ataque servicios
  ajenos ni envíe mensajes a terceros para demostrar el problema.
- Evidencia anonimizada: ID de operación, estado, código de salida y fragmentos de
  log imprescindibles. Separe lo observado de las hipótesis y de lo no ejecutado.
- Mitigación temporal conocida, si existe, sin afirmar que sea una reparación probada.

No adjunte tokens, cookies, QR de vinculación, claves, archivos de configuración
privados, bases de contactos, perfiles Brave, conversaciones completas ni documentos
reales de clientes. Un hash o una ruta también pueden revelar información: revise
su necesidad y sustituya nombres personales por identificadores ficticios.

## Modelo de confianza y controles existentes

ADL puede acceder a archivos, procesos, Git, proveedores y servicios externos con
los permisos que le conceda el usuario del sistema. **No es un sandbox del host ni
un servicio diseñado aquí como plataforma pública multiusuario.** Las validaciones
de rutas, revisiones y confirmaciones reducen determinados riesgos; no aíslan un
proceso comprometido con permisos del usuario ni sustituyen los controles del sistema.

### Proveedores y sesión del host

Se deben reutilizar los conectores y el canal ya configurados en el host cuando
corresponda. No copie tokens a otra candidata, contenedor, agente o carpeta para
aparentar una conexión. El adaptador Codex utiliza el proceso del proveedor y
retira de su entorno hijo determinadas variables de claves API; el registro de
proveedores utiliza un almacén de credenciales admitido. Esto no prueba una
inferencia real ni garantiza que todos los proveedores compartan idéntico modelo
de autenticación. Revise los destinos y permisos del proveedor utilizado.

### Propuestas, autorizaciones y operaciones destructivas

Mantenga separados propuesta, revisión, autorización, ejecución y recibo. Revise
la identidad del recurso y el alcance exacto antes de confirmar una acción.

- Borrar un perfil de agente exige confirmación, revisión SHA-256 actual y ausencia
  de trabajo activo comprobado; conserva una copia local de recuperación antes de
  retirar el perfil. Esa copia puede contener datos privados y necesita protección.
- El borrado permanente de una conversación exige su estado de papelera y revisión
  vigente, dentro del proyecto correspondiente; no es un mecanismo de borrado de
  todas las trazas o copias externas.
- El SDK Workspace limita operaciones a workspaces administrados bajo un padre
  explícito, comprueba revisiones/huellas y confirmación de operación e identidad,
  y rechaza determinados enlaces y contenidos sensibles. No lo trate como un
  ejecutor de comandos arbitrarios ni como garantía de detección de todo secreto.

Una confirmación caducada o una revisión antigua no debe sustituirse automáticamente
por otra para forzar el resultado. Si falla una escritura o una copia de recuperación,
conserve el recurso y revise el error antes de repetir la operación.

### Contactos, Comunicaciones y WhatsApp

La agenda compartida conserva identificadores y separa los contactos actuales de
los snapshots de destinatario de los borradores. Un cambio de contacto no cambia
silenciosamente un borrador ya revisado. Revise teléfono exacto, texto, adjuntos y
calendario antes de confirmar; un contacto de sólo email no es un destino WhatsApp.

Los borradores y su programación persisten localmente. La salida debe vincularse
a la operación y al recibo correspondiente. Los estados `draft`, `sending`, `sent`,
`failed`, `uncertain` y `cancelled` no son intercambiables: un clic, una conexión o
un proceso vivo no prueban envío. Los intentos interrumpidos o con recibo ausente
pueden quedar `uncertain`; no se reintentan automáticamente como si no hubieran
ocurrido. Compruebe la entrega antes de autorizar cualquier nuevo intento.

WhatsApp utiliza un perfil Brave propio, persistente y vinculado por QR. Su control
comprueba identidad del proceso, perfil y puerto CDP local; una propiedad no
confirmada no autoriza cerrar otro navegador. Proteja el perfil como una sesión
privada: no lo publique ni lo incluya en ZIPs, capturas o repositorios. El puerto
CDP no debe exponerse a redes externas. El estado `unknown` indica falta de
observación suficiente, no conexión o desconexión demostrada.

El SDK Contactos protege determinados secretos OAuth en su almacenamiento privado
(incluido DPAPI en Windows); esto no significa que la base de contactos y todas
las evidencias estén cifradas. Los consentimientos Google y las sesiones WhatsApp
se gestionan con sus proveedores: conservar archivos no equivale a revocar acceso.

### Docker y observabilidad

La configuración de desarrollo publica puertos en `127.0.0.1`, limita privilegios
y monta los directorios fuente del frontend en sólo lectura. Conserva datos en
volúmenes propios. Esos controles se refieren a esa configuración concreta, no a
cualquier despliegue derivado ni a todos los archivos del contenedor.

El frontend puede actuar como puente hacia una API del host que ya tiene acceso a
proveedores y datos. `localhost` no sustituye una autenticación para exposición
pública ni impide el acceso de otros procesos del mismo equipo. No publique el
proxy, la API, CDP, Jaeger o los receptores de trazas en una red compartida sin un
diseño y revisión específicos. Una traza de Jaeger demuestra observaciones
registradas, no autoriza una acción ni acredita por sí sola el resultado útil.

## Instalar y trabajar con menor exposición

1. Obtenga una fuente o candidata de procedencia identificable. Compruebe inventario
   y SHA-256 contra un manifiesto obtenido por una vía de confianza; un manifiesto
   alojado junto al archivo no constituye por sí mismo una firma del autor.
2. Revise contenido, dependencias declaradas, scripts y destinos antes de ejecutar.
   Use un entorno y datos de prueba aislados para una candidata experimental.
3. Conserve la instalación anterior y una copia protegida de los datos que necesite
   recuperar. No mezcle perfiles, credenciales o volúmenes de pruebas con producción.
4. Utilice permisos de usuario suficientes para la tarea, evitando elevarlos sin
   necesidad. Configure el padre Workspace y los destinos externos explícitamente.
5. Mantenga los puertos de desarrollo locales. No monte el socket Docker ni carpetas
   privadas adicionales para resolver un fallo sin revisar su alcance.
6. Antes de usar un proveedor o enviar resultados, compruebe la sesión, identidad,
   autorización y destinatario reales. Las pruebas con mocks, fixtures o API health
   no sustituyen esas comprobaciones.

## Evidencias y divulgación

Conserve el original de una evidencia necesaria en un almacenamiento privado con
acceso limitado. Prepare una copia anonimizada para revisión, manteniendo IDs y
huellas que permitan vincularla al candidato sin revelar datos personales. No se
declara aquí un plazo automático de retención ni una eliminación global: revise
por separado bases locales, copias `.deleted`, adjuntos, perfiles, logs, trazas,
volúmenes y backups antes de compartir o retirar información.

Coordine cualquier divulgación técnica por un canal privado disponible y acuerde
qué información puede hacerse pública. Documente alcance, mitigación, candidata
corregida y pruebas realizadas; no publique secretos ni atribuya una corrección a
versiones que no se hayan comprobado.
