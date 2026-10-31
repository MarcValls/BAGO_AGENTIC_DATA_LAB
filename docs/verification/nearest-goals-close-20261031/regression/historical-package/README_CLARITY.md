# Reconciliación histórica — readme-clarity-20261022

Fecha: 2026-10-31. Estado: cierre histórico EXECUTED y VERIFIED por el controlador
original; revisión independiente de los cambios de reconciliación PENDING.

## Resultado ejecutado

I01 estaba CLAIMED aunque su comprobación final real había pasado el 22 de
octubre. Se completó su handoff mediante el controlador original Suite1.4.2,
sin migrar el estado ni alterar recibos, inputs u outputs antiguos. El controlador
aceptó el handoff, cerró la misión como CLOSED / VALIDATED_SCOPED_TASK y produjo
verify PASS después del cierre.

El handoff consume sin modificar el recibo 70abb24fbde1402c8cde8876b3bd4521:
generador completo y check --skip-tests exit0; JUnit 550 casos, **549 PASS y
1 SKIP**. El segundo comando no ejecutó la suite. SHA del output RESULT.json:
d060c05e3a17dfa047bd27d02318d6fc719c659d84a0dc1aea36c97eab7961d9.
Se conserva la revisión independiente histórica V01 PASS, sin atribuirla a los
nuevos cambios del 31 de octubre.

Publicación contrastada: candidato 64a88fbc30bb1b2c0a4cd516281c71be1f65748b,
PR63 MERGED, merge 2d521170fdf651da482b5bf9d5b229a41412a8d2. Ambos tienen árbol
0012569d5abbd89a48781cd9603baa70674b732a. El README publicado coincide por SHA
con la salida histórica. CI 39823019847 completed/success para el SHA exacto;
el CI 39823364746 CANCELLED y el antiguo agregado FAIL permanecen intactos.

## Intentos y conservación

El teamctl actual rechaza el estado antiguo como LEGACY_UNVERIFIED. Se conserva
ese FAIL; el controlador original conserva identidad exacta y verifica PASS.
No se presenta el cierre como gate del protocolo moderno.

El primer draft nuevo fue rechazado porque next_consumers nombraba consumidores
no declarados en la misión. Se conservan draft, script y recibo FAIL; no se
registró ni alteró el estado con ese intento. El segundo draft usa lista vacía
porque I01 es terminal y fue aceptado. No se reescribió el intento rechazado.

Evidencias nuevas: evidence-reconciliation.json, protected-before.json,
legacy-I01-handoff-submission.json (FAIL),
legacy-I01-handoff-submission-attempt2.json (PASS), legacy-close.json y
legacy-verify-after.json. Estado y eventos anteriores están en preserved/.
El nuevo handoff aceptado se conserva en reviews/I01/ y en el runtime local.

Comprobación reproducible desde la raíz del repositorio:

```powershell
python -B .bago/goals/readme-clarity-20261022/reconciliation-20261031/reconcile.py
python -B .bago/goals/readme-clarity-20261022/reconciliation-20261031/verify_idempotence.py
```

El segundo script conserva IDEMPOTENCE.json: repetir --apply después del cierre
no cambia estado, eventos ni ninguno de los archivos históricos protegidos.

## Límites y revisión pendiente

La aceptación se limita al candidato documental histórico. No valida el checkout
actual ni convierte los criterios antiguos de presentación en requisitos vigentes
frente a decisiones posteriores. No se editaron fuentes ni README. Pruebas de
producto actuales, nueva generación README, runtime y proveedores: NOT_RUN.

El autor no se atribuye independencia ni acepta sus propios cambios. El nuevo
addendum, los scripts y la transición I01 requieren la revisión independiente
coordinada por el orquestador antes de cerrar el lote de reconciliación.
