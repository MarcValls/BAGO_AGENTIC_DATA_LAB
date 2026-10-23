# Servicios de la candidata integrada

Este documento describe las entradas del código integrado. Las pruebas de cada
fase conservan su candidato de origen; la aceptación final se registra en
[integración](../integration/CONTRACT.md). No presenta servicios externos como
conectados por el hecho de disponer de una pantalla.

El [manual de uso por pantallas](../public-web/MANUAL.md) reúne los pasos de
trabajo. La aplicación lo sirve en `/manual`. Las instrucciones extensas están
en esa guía; cada pantalla conserva las acciones, estados y confirmaciones de
su operación.

## Lectura web pública

El Chat permite autorizar una lectura por turno, conversación e interlocutor.
Las fuentes conservan URL, captura, líneas y huellas de integridad. Un error
posterior del proveedor conserva el estado fallido y la evidencia parcial
disponible. Disponer de esta herramienta no demuestra por sí solo una
inferencia real ni el envío de un resultado.

El [núcleo y CLI independientes](../../src/web_research/README.md) pueden usarse
sin levantar ADL. La lectura no ejecuta scripts ni envía formularios. Los
permisos, límites, fuentes y procedimiento de comprobación se describen en el
[manual](../public-web/MANUAL.md).

## Contactos

**Contactos** permite mantener la agenda local y preparar la selección de Google.
Comunicaciones utiliza los mismos identificadores canónicos. Un contacto con sólo
email sigue siendo válido en la agenda; WhatsApp exige un teléfono adecuado.
Preparar un mensaje conserva una instantánea del destinatario en el borrador.

El núcleo independiente está en
[`src/contacts_service/core.py`](../../src/contacts_service/core.py).
Puede ejecutarse sin ADL con Python y un directorio privado de datos:

```powershell
python src/contacts_service/core.py --help
python src/contacts_service/core.py --root C:/BAGO_DATOS/contactos list
```

Google requiere configuración y consentimiento propios. El funcionamiento vivo
no se deduce de las pruebas sintéticas. [Contrato](../contacts/CONTRACT.md).

## Comunicaciones

La pantalla y las tarjetas de Chat comparten borradores e identificadores.
Revisar, confirmar, programar, cancelar y ejecutar son operaciones distintas.
La agenda compartida conserva los IDs heredados; un conflicto se informa antes
de consumir el contacto. Un envío de resultado incierto no se reintenta
automáticamente: hay que revisar su recibo.

El núcleo Python
[`CommunicationService`](../../src/communications/service.py) acepta sus
dependencias explícitamente y se puede utilizar sin importar el servidor ADL.
El [worker](../../src/communications/worker.py) separa el despacho de la interfaz.
El adaptador ADL añade la agenda compartida, sin exigir BAGO al núcleo.
[Integración, conciliación y límites](INTEGRATION.md).

## WhatsApp

Settings contiene la configuración de una sesión propia y persistente, vinculada
mediante QR. La pantalla distingue los estados devueltos por el servicio; guardar
configuración no demuestra conexión. CDP, perfil de navegador y destinatario son
recursos distintos. Los perfiles y las credenciales son privados.

El [gestor de sesión](../../src/whatsapp/session.py) y el adaptador de transporte
se pueden invocar desde Python sin montar la interfaz ADL.
No se autoriza un envío por mostrar una propuesta o por abrir la pantalla.
[Contrato de sesión](../whatsapp/CONTRACT.md) · [Seguridad](../../SECURITY.md).

## Workspace

Workspace y su tarjeta de Chat utilizan la misma propuesta revisable. Crear un
proyecto prepara contexto, estado y continuidad; vincularlo debe mostrar sus
archivos efectivos. El editor exige la revisión actual del archivo. La papelera
y las operaciones Git conservan sus confirmaciones y límites propios.

```powershell
python src/workspace_sdk/workspace_service.py --help
```

El SDK independiente se distribuye en
[`src/workspace_sdk`](../../src/workspace_sdk/workspace_service.py).
Los planes GitHub remotos no acreditan creación de repositorios, push o merge.
[Contrato de Chat](../workspace/CHAT_CONTRACT.md) ·
[SDK y operaciones](../workspace/README.md).

## Agentes y conversaciones

La barra lateral agrupa gestión, creación, ejecución y evaluación. La edición
preserva modelos sin asignar; eliminar un perfil necesita una revisión actual y
conserva su historial. La papelera de conversaciones ofrece eliminación
definitiva con confirmación, diferenciada de mover a la papelera.
[Guía del frontend](../readme_frontend.md) ·
[Gestión de agentes](../agent-management/CONTRACT.md).

## Inspect por conversación

El Chat transmite conversación y traza a Inspect. La consulta
`GET /api/conversations/{id}/inspection` permite seleccionar únicamente trazas
referenciadas por esa conversación; no sustituye datos ausentes por una demo.
Los registros antiguos sin hash persistido se muestran como `legacy_unverified`.
Una traza no equivale a un paquete de decisiones, autorizaciones o evaluación.
Las vistas globales y la demo histórica se identifican por separado.

El núcleo independiente
[`inspection`](../../src/observability/chat_inspection.py) recibe una conversación
y raíces de trazas explícitas. La demostración con los identificadores de octubre
es un REPLAY de evidencia capturada, no una inferencia nueva.
[Contrato y límites](../inspect-correlation/CONTRACT.md).

## Desarrollo y comprobación

[Docker](../../infra/dev/README.md) prepara entornos aislados. Su prueba de recarga
sintética no sustituye la comprobación sobre la fuente integrada final. Los
recibos positivos, negativos y de recuperación deben identificar fuente, proceso
y contenedor. [Política de seguridad](../../SECURITY.md).
