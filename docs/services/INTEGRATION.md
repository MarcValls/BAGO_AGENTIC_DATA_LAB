# I02 — Integración backend de servicios

## Alcance y procedencia

Base común: `c5a78d33fbf5da608f550c4e8809eb6a8cb1be4c`.
`docs/integration/INPUTS.json` es la identidad de entrada; no se ha modificado.
`source-provenance.json` recoge las fuentes backend comprobadas antes de copiar.
`composition-manifest.json` compara SHA de cada entrada/destino y funciones
superiores de los cinco server.py. Los SDK se conservan byte a byte; las
adaptaciones viven en rutas, composición y puente, no en sus núcleos.

`server.py` se construyó aplicando cada delta contra la base con `git merge-file`.
Se resolvieron tres regiones: importaciones, enum/propiedades de decisiones y
registro de routers. Se conservaron gestión, borrado definitivo de conversaciones,
Comunicaciones/WhatsApp, Contactos y Workspace. Las propuestas de comunicaciones
y workspace coexisten y sus referencias permanecen en la conversación.
Se completó el retorno de ambas propuestas en el bucle de lectura con herramientas
y en respuestas estructuradas sin tool_calls; este cambio es adaptación de composición.

Los archivos `composition/*.txt` preservan entradas normalizadas a LF y el resultado
con conflictos previo a resolver. Son evidencia de integración, no código ejecutable.
Los helpers `compose_backend.py` y `resolve_composition.py` describen pasos históricos;
NO deben ejecutarse sobre una candidata posterior: sobreescribirían su composición.

## Contrato de agenda compartida (adaptación sin nuevo DTO)

- `/api/contacts/v1/contacts` conserva el contrato AddressContact con revision/email.
- `/api/communications/contacts` conserva `{contacts:[{id,name,phone}]}` y su POST.
- En ADL ambos utilizan `BAGO_CONTACTS_STATE_DIR` o el mismo directorio local de
  Contactos. El bridge es perezoso y no lee credenciales ni crea archivos al importar.
- `CommunicationService(..., contacts_store=...)` acepta un repositorio inyectado
  con `list()`, `add(name,phone)` e `import_legacy(records)`. Sin él conserva su modo
  standalone original. No requiere registrar un proveedor ni un canal nuevo.
- Crear un borrador resuelve el ID canónico y conserva snapshot `{id,name,phone}`.
  La edición o eliminación posterior del contacto no cambia un borrador existente.
  Crear/editar un borrador no confirma ni envía.
- Contactos con sólo email siguen siendo gestionables, pero no son destinatarios
  WhatsApp. Se exige teléfono E.164 con dígitos ASCII al preparar borrador.

### Conciliación heredada

Al primer uso de la agenda de Comunicaciones, sus filas legacy se importan en una
transacción al almacén canónico preservando ID y destino. La base original y los
borradores no se borran ni reescriben. `communications_legacy_imports` conserva la
huella de cada fila conciliada; así un contacto editado o eliminado en la agenda
canónica no se sobrescribe ni reaparece desde la copia histórica.

Colisiones de teléfono/ID, datos inválidos o un origen legacy cambiado después de
conciliar producen un error explícito y rollback de la importación de contactos.
No hay consolidación silenciosa de IDs. Resolver esas colisiones requiere revisión
explícita; esta fase no inventa una política de fusión ni borra datos anteriores.
Si falla almacenamiento, el puente devuelve error y mantiene el origen.

## SDK y dependencias

Contacts core SHA `01c2d22ceed56fce41e1350a6fe78c46d31ae187f25ff13d279f761c06330972`.
El `REPAIR.patch` tiene hash raw CRLF `5996e630…`; su forma LF es `89b54bfb…`,
la huella que ya figura en PROVENANCE. No se alteró el manifiesto histórico.
La referencia `history/UPSTREAM_SOURCE.py` de ese PROVENANCE ya está ausente en la
entrada Contacts: no se afirma que esté entregada. La continuidad/licencias y esa
fuente histórica deben resolverlas I07 antes de empaquetar.

Workspace core y primitivas quedan byteidénticos a las entradas fijadas. La carga
por paquete conserva el guard de colisiones de nombres de módulos.
Los tests externos usan copias temporales de los SDK **de esta candidata**, con
los tests y fixture sintético de sus proyectos fuente. No ejecutan una instalación
activa ni reutilizan sus resultados. `external-inputs.json` fija esas fuentes.

Dependencias de WhatsApp/requirements se integran en I05 por root según
INPUTS_ADDENDUM_01, fuera del scope de escritura I02.

## Verificación y límites

`run_acceptance.py` genera logs y resultados nuevos bajo evidence/I02 y se ejecuta
por `teamctl run-check acceptance`. Ver `results.json` y recibo gestionado para los
resultados finales de esta fase. El ensayo focal previo de 205 PASS es histórico
respecto a las últimas adaptaciones y no se suma al ensayo final.

I02 entrega snapshots inmutables; I05/I06 deben verificar el conjunto final tras
cualquier reparación. UI visual, Docker, Google vivo, proveedores y WhatsApp real
son NOT_RUN en esta fase. README generado y cierre global pertenecen I07/I08.

### Primera ejecución gestionada: fallo de harness conservado

Ejecución `8c98ef672e5c46b2b1153dd012a4db83`: FAIL, 26 fallos por
`ZoneInfo Europe/Madrid unavailable`, 200 PASS; SDK externos 14 y 19 PASS.
El subproceso de pruebas no recibía la raíz de dependencias aislada de manera
explícita y el output declarado `acceptance.json` no coincidía con `results.json`.
Se conserva bajo `evidence/I02/attempt01`; se corrigió exclusivamente el harness
para pasar `PYTHONPATH` en `env` y declarar el archivo que realmente produce.
No se cuentan esos resultados como aceptación del estado final.

Revisión final de conciliación: el POST de contactos de Comunicaciones también
concilia antes de crear, evitando fabricar un segundo ID si el primer uso de la
agenda fue una creación. Se añadió aceptación para ese orden y para fallo real
inyectado de persistencia; la ejecución anterior PASS se conserva en attempt02,
antes de repetir las comprobaciones afectadas sobre los bytes finales.
