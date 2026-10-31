# Reconciliación histórica — github-update-20261022

Fecha: 2026-10-31. Estado: ejecución y comprobación local VERIFIED; revisión
independiente de este addendum PENDING. La misión histórica de revisión ya estaba
CLOSED / VALIDATED_SCOPED_TASK y se conserva sin reabrir ni re-firmar sus entregas.

## Alcance cerrado acreditado

- Submisión ADL_PUBLICATION_TEST_REVIEW_20261022: V01 DONE, revisión independiente
  histórica y recibos originales revalidados por el controlador que los emitió.
- Publicación de la entrega: commit Windows f2b34e51ce2e3607490f710f60070f1e4de5759e
  es ancestro del candidato publicado b0b2f2a2079019fe80e82b836e13c5580a189b70.
- PR62 fusionada como f253f3700990943755e63717a93d3be99f0e19fa. Árbol de merge y
  candidato idéntico: accfe27115fed2854d791434d9866ebd39210b56.
- CI 39813814372 completed/success para ese candidato exacto. Las respuestas
  GitHub fueron recuperadas por el orquestador en esta sesión y se conservan en
  github-pr62.json y github-ci.json; sus SHA figuran en evidence-reconciliation.json.
- JUnit Windows conserva 537 casos: **536 PASS y 1 SKIP**, no 537 PASS. La CI
  posterior documenta 539 PASS, frontend 127/49/13 y build; no se suman ejecuciones.

## Verificación ejecutada y conservación

El teamctl actual rechaza el estado antiguo como LEGACY_UNVERIFIED. Se conserva
ese FAIL y no se declara compatible con el protocolo moderno. El controlador
original Suite1.4.2, localizado mediante START_RECEIPT.json y con identidad exacta
comprobada por su propio verify, produce PASS/CLOSED. No se migró el estado.

protected-before.json registra hashes de misión, inputs congelados, handoffs,
recibos, logs y outputs históricos. preserved/ conserva estado y eventos previos.
El script comprueba que esos bytes no cambian después de la operación. No hubo
escritura en fuentes, README, configuración global ni operaciones Git mutantes.

Evidencias: evidence-reconciliation.json, legacy-verify-after.json,
protected-before.json e IDEMPOTENCE.json. El último recibo se genera al ejecutar
verify_idempotence.py y demuestra que repetir --apply no cambia estado, eventos
ni evidencia protegida.

Comprobación reproducible desde la raíz del repositorio:

```powershell
python -B .bago/goals/github-update-20261022/reconciliation-20261031/reconcile.py
python -B .bago/goals/github-update-20261022/reconciliation-20261031/verify_idempotence.py
```

## Límites y aceptación pendiente

No es validación del checkout actual, de cambios posteriores, de proveedores,
Docker ni del producto BAGO5 completo. Pruebas nuevas de producto y generación
README del checkout actual: NOT_RUN. Los gates históricos se consumen como
ejecuciones históricas, sin cambiar fechas ni cantidades.

Dictamen del autor: elegible para aceptación independiente del cierre histórico
de publicación; **no se autoaprueba esta reconciliación**. El orquestador debe
recibir y validar el dictamen independiente antes de dar por terminado su lote.
