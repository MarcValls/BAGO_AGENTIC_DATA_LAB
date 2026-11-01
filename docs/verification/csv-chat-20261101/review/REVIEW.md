# Revisión independiente de lectura CSV desde el chat principal

**Resultado del ámbito W12: VERIFICADO — 57/57 casos HTTP satisfactorios.**

La revisión se hizo después de congelar los handoffs W02, W03 y W04. El verificador
no editó la implementación. Añadió `tests/test_csv_chat_flow.py` y esta evidencia.
El check gestionado `flow`, ejecución `b04ecccbdb5c4b33b568a715e70a2218`, terminó
con 57 PASS en 95,58 segundos. Véanse [SUMMARY.json](SUMMARY.json),
[pytest.log](pytest.log), [MANAGED_CHECK.json](MANAGED_CHECK.json) y los resultados
individuales de [http/](http/).

## Qué demuestra esta verificación

Los casos usan peticiones HTTP reales mediante `TestClient`, el enrutador y las
funciones de producción, archivos reales, `ProjectPermissions`, el registro
existente `WorkspaceReadAuthorizations`, el lector acotado, el document toolkit,
los cálculos con Decimal y el almacenamiento SQLite de conversaciones. Cada caso
se ejecuta en un proceso nuevo con proyecto y estado sintéticos en `/tmp`.

**Solo se controla la selección y la interpretación del proveedor.** El proveedor
de prueba recibe las filas realmente leídas y devuelve un plan `query_csv`.
No se sustituyen respuestas HTTP, permisos, lectura, parser, cálculo ni
persistencia. Las observaciones de IO y los puntos de espera de los casos
adversariales sirven para introducir una revocación, STOP o cambio real en la
frontera correspondiente. No se ejecutó un modelo remoto.

Se contrastan los resultados con constantes calculadas independientemente, se
recalculan los SHA-256 de petición, plan y resultado, y se comparan el POST,
un GET posterior y una conexión SQLite adicional de solo lectura. Los 57 casos
registran los mismos hashes de las fuentes de implementación y de la prueba;
también verifican el hash del servidor realmente importado. No hay una segunda
generación del modelo que reescriba los resultados calculados.

## F10, F11 y F12 reproducidos

El CSV utilizado tiene exactamente **183 bytes UTF-8**, saltos LF y salto final,
SHA-256 `8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5`.
Es el contenido reconstruido de la evidencia histórica, conservado en
`../parser/pedidos-original.csv`.

| Pedido | Cliente | Cálculo contrastado | Importe |
| --- | --- | --- | ---: |
| P001 | Alba | 12 × 18,50 × (1 − 10/100) | 199,80 |
| P002 | Bruno | 6 × 9,00 × (1 − 0/100) | 54,00 |
| P003 | Carmen | 8 × 6,25 × (1 − 5/100) | 47,50 |

Pendientes: **247,30**, filas físicas 2 y 4. Total general: **301,30**, filas 2,
3 y 4. Los decimales de la respuesta pueden conservar ceros adicionales;
la comparación se realiza con Decimal y los valores originales.

| Recorrido | Primera condición comprobada | Resultado tras selección y autorización exactas | Evidencia |
| --- | --- | --- | --- |
| F10 | La ruta escrita en chat, sin READ ni grant, no permite leer; el chat explica que no ha leído ningún archivo | Tras guardar READ y autorizar ese CSV para esa pregunta, una lectura real, una interpretación, respuesta correcta y cuatro mensajes persistidos contando el primer intercambio denegado | [F10.json](http/F10.json) |
| F11 | El selector obtiene metadatos sin abrir el CSV; tener READ sin grant produce `READ_AUTHORIZATION_REQUIRED` | Metadatos → autorización existente con `csv_request` → `/api/chat/control`; resultado correcto y dos mensajes persistidos, sin llamada a ingesta, conocimiento o document corpus | [F11.json](http/F11.json) |
| F12 | Guardar READ no concede por sí solo permiso para una petición CSV | El grant de la pregunta y opciones exactas permite leer y responder con fuentes, recibo y resultado persistidos | [F12.json](http/F12.json) |

Los tres casos comprueban que el archivo original permanece intacto. La revisión
no declara que escribir una ruta equivalga a consentimiento ni que READ guardado
sea una autorización general nueva. El recorrido reparado exige seleccionar el
archivo y autorizar la consulta concreta.

La ejecución de navegador de W04 añade evidencia del recorrido **principal chat
→ Recursos → Consultar archivo → CSV**, tanto en escritorio como en móvil,
con backend real y proveedor controlado: `../frontend/causal-browser/`. W12
verifica de forma independiente su transporte y las fronteras del servidor.

**R19–R21 siguen siendo evidencia histórica de visualización Tabla/Texto.** No
se utilizan para demostrar lectura desde chat, ejecución de consultas ni
autorización. Su evidencia y los FAIL/BLOCKED originales de F10–F12 permanecen
sin modificaciones.

## Fronteras verificadas

| Grupo | Casos y resultado observado |
| --- | --- |
| Autorización | Ausente, inventada, caducada, revocada y reutilizada: denegación, sin segunda lectura ni datos de resultado. Un ticket genérico no se convierte en un grant CSV |
| Identidad y contexto | Propietario, tipo de propietario, conversación, revisión y conversación archivada: rechazo antes de IO. Cambiar la pregunta, ruta, delimitador o separador decimal invalida la petición |
| Proyecto y política | Otro proyecto, rebinding A→B→A, READ revocado y READ revocado/reconcedido: el grant anterior no se reutiliza. La selección exacta no se amplía al otro CSV del mismo directorio |
| Rutas | Absoluta, traversal, unidad Windows, ruta interna oculta, enlace simbólico y enlace duro: no se autoriza ni se lee contenido |
| Límites y CSV inválido | Límite de bytes, más de 250 líneas físicas, UTF-8 inválido, comillas abiertas, anchura irregular y cabeceras duplicadas: no se calcula una respuesta parcial ni se envían esos datos al intérprete |
| Interpretación | Columna inexistente, operador ejecutable no admitido, ausencia de plan, varios planes, claves JSON duplicadas, excepción del proveedor, número incompatible con el separador y división por cero: respuesta explícita de error sin inventar valores |
| Cambios concurrentes | Modificación antes de leer, dentro del `read` real, durante la interpretación y sustitución por otro inode: resultado retenido; el recibo distingue si ya hubo IO |
| Revocación y caducidad en vuelo | DELETE de la autorización o vencimiento mientras el proveedor espera: no se publica el análisis. DELETE inmediatamente antes de persistir la respuesta también impide publicar los datos |
| STOP existente | Misión creada y pausada con el controlador real de teamctl: antes de IO no hay lectura ni proveedor; durante el proveedor o antes de publicación se retienen resultados. No se modifica el runtime histórico del repositorio |
| Interpretaciones explícitas positivas | CSV con decimal coma y separador punto y coma: resultados correctos. `limit=1`: solo se muestran subconjuntos, pero los agregados siguen usando las tres filas autorizadas y totalizan 301,30 |

La evidencia distingue `executed=false / DENIED` de
`executed=true / WITHHELD`. Una revocación posterior a la lectura no deshace los
bytes que ya se leyeron legítimamente; sí impide publicar el resultado pendiente.
En los casos negativos, la respuesta y el historial no contienen las celdas
Alba/Bruno/Carmen, las celdas del archivo no seleccionado o externo, ni el
diagnóstico privado de la excepción del proveedor.

### Hallazgo P1 previo: autoridad obsoleta después de esperar un lock

La inspección preliminar encontró `CSV-AUTH-WAIT`: el prototipo comprobaba el
grant antes de esperar por la lease de política. Se retuvo ese lock, se inició la
consulta, se revocó el grant y se liberó el lock. La observación preliminar fue:

```text
grant_checked
revoked_while_waiting_for_policy_lease
csv_read_begin_after_revoke=True
csv_read_ok=True
```

El prototipo retenía después la respuesta, pero ya había leído tras la revocación.
El hallazgo se comunicó al implementador antes del handoff. La corrección reutiliza
las leases existentes, con orden **política → STOP → grant**, revalidación después
de esperar y retención de la lease del grant durante IO o publicación acotados.
No retiene estos locks durante la llamada al proveedor.

La reproducción independiente posterior comprobó las seis combinaciones
lectura/publicación × revocación/caducidad/STOP mientras se esperaba la política:
cero efectos posteriores y el código correspondiente. W02 conservó regresiones
en `tests/test_csv_chat_access.py`; W12 verificó además las fronteras HTTP reales
de revocación y STOP durante proveedor y antes de publicación. Estado del
hallazgo: **CLOSED**.

### Incidencia de persistencia del entorno

La QA móvil detectó una conversación que respondió revisión 2 y luego apareció
en revisión 0. El ensayo independiente observó dos sustituciones de inode con
contenido anterior en bases sintéticas del directorio compartido, incluso con
cierre explícito de conexiones. No identificó al actor que sustituyó los archivos.
Se conservaron el FAIL y su GET posterior; no se aplicó un parche especulativo a
la persistencia. El contraste en `/tmp` pasó 6/6 casos, 3.000 escrituras.

Véase [SQLITE_RUNTIME_INCIDENT.md](SQLITE_RUNTIME_INCIDENT.md), que incluye el
script, las doce observaciones y el alcance de la conclusión. La ejecución causal
de navegador y esta matriz HTTP usaron estado mutable en `/tmp` y verificaron la
persistencia. La anomalía previa no queda borrada ni atribuida sin evidencia a una
causa concreta del producto o del host.

## IMPLEMENTADO, VERIFICADO y NOT_RUN

| Clasificación | Alcance |
| --- | --- |
| **IMPLEMENTADO** | Selección CSV en chat principal, autorización ligada a pregunta/opciones/contexto, lectura acotada mediante componentes existentes, parser compartido, plan finito, cálculo determinista, respuesta con procedencia y revocación en vuelo; fuentes congeladas W02/W03/W04 |
| **VERIFICADO** | 57 casos HTTP de W12 con IO/política/SQLite reales y proveedor controlado; F10–F12 con bytes históricos; navegador escritorio/móvil de W04; preservación del histórico, runtime legacy, `local_rag.py` y `library.py` |
| **NOT_RUN** | Modelo remoto real y su precisión semántica; Windows; instalación y proyectos reales del usuario; despliegue; integración global de STOP en otros recorridos de chat |

Los casos `legacy_stop` e `invalid_stop` verifican **cero lecturas** y
`STOP_STATE_UNVERIFIABLE`. Un proyecto con runtime teamctl antiguo o no verificable
queda bloqueado deliberadamente. No se ha migrado ni borrado ese estado, y el PASS
en las fixtures nuevas no prueba que un proyecto legacy del usuario pueda ejecutar
la consulta sin resolver su estado mediante el procedimiento existente.

El modelo propone la interpretación. La validación impide planes no admitidos y
el cálculo contrasta con los datos, pero **no prueba que cualquier plan válido
represente siempre la intención del usuario**. La fórmula, filtros y opciones
aplicadas se muestran para revisión. No se presenta esta prueba controlada como
medición de exactitud de un modelo real.

El preflight se conserva: 55 PASS y dos expectativas incorrectas de códigos en la
prueba (`CSV_MALFORMED` para autodetección con anchura irregular y
`CSV_HEADER_DUPLICATE` para cabecera duplicada). Se corrigieron solo las
expectativas del test y se repitió la matriz completa mediante el check formal.
No se modificó el producto para hacer pasar estas pruebas.

## Reproducción

```bash
python -m pytest -q tests/test_csv_chat_flow.py
```

Se requieren las dependencias de test del repositorio. Los casos crean y eliminan
fixtures propias en `/tmp`; no usan el proyecto real ni llaman a un modelo remoto.
`run_verification.py` muestra el comando, el manifiesto y la preservación histórica
utilizados para esta evidencia. Rechaza sobrescribir su directorio final existente:
una repetición debe conservar los resultados anteriores y usar otro destino
revisado. No se han fusionado ni publicado cambios desde W12.
