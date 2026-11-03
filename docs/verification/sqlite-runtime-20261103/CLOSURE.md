# Cierre acotado de la investigación

**Investigación y entrega diagnóstica completadas; persistencia NO REPARADA; cierre técnico global incompleto.**

| Comprobación | Resultado | Alcance |
| --- | --- | --- |
| Evidencia original y SHA-256 | PASS | Histórico preservado; casos 3 y 7 siguen FAIL |
| Contraste de conexiones `main` / PR #116 | PASS | Cierre de recursos comprobado; reparación no demostrada |
| Ensayos pasivos nuevos | 14 PASS, 1 FAIL | 7.000 mensajes en los catorce éxitos; nuevo `malformed` preservado |
| Controles deliberados de pérdida | FAIL esperado de persistencia; PASS del diagnóstico | Sustitución física y sobrescritura del mismo inode |
| Tests centrados finales | PASS | 21 tests, incluidos ocho casos diagnósticos |
| Revisión independiente | PASS | Tres controles adicionales; fuentes verificadas; P1 de producto abierto |
| Generador README con suite completa | FAIL | Primera variante instrumentada: 37 fallos, 2.072 éxitos, tres omitidos; log íntegro conservado |
| Suite completa de la base intacta | FAIL | Base `6173ade`: mismos 37 identificadores fallidos, 2.066 éxitos, tres omitidos |
| Suite completa de la variante final | NOT_RUN | La última ampliación se verificó mediante los 21 tests centrados; no se extrapola a toda la suite |
| README regenerado con `--skip-tests` | PASS de generación; suite NOT_RUN | 2.114 casos recogidos; README sin diferencias |
| README `--check --skip-tests` | PASS de consistencia; suite NOT_RUN | No acredita ejecución de los tests |
| Revisión de whitespace en código/tests/docs | PASS | Los logs y el parche bruto conservan sus bytes, incluidos espacios finales |
| Windows / instalación real / móvil original | NOT_RUN | Fuera del entorno disponible |
| Atribución mediante `strace` | NOT_RUN | `ptrace` denegado antes del lanzamiento del ensayo |

`implementation/full-suite-comparison.json` conserva los 37 identificadores coincidentes. Incluyen fallos de exportación OTel y de fixtures DOM; en estos últimos falta `frontend/node_modules/jsdom`. Se reprodujeron sin los cambios de esta entrega. No se reparan áreas ajenas ni se presenta como PASS una suite fallida. La causa de cada fallo ajeno no se establece únicamente por esa coincidencia.

La primera ejecución completa se inició antes de ampliar de seis a ocho casos diagnósticos y de terminar los ajustes del ensayo. Sus resultados se conservan con ese alcance, sin adjudicarlos a una ejecución completa de las fuentes finales. El manifiesto W01, los 21 tests finales y la revisión W02 se refieren a las fuentes finales.

La misión administrativa de auditoría terminó con `VALIDATED_AUDIT_SCOPE` y `product_state=FINDINGS_REPORTED`. Esto valida el alcance de la auditoría, no el producto. Se preservó el runtime histórico del repositorio usando un runtime independiente dentro del objetivo actual. La observación de configuración de rsync se añadió separadamente después de los handoffs; no se reescribieron los informes independientes para incorporarla.

Base inicial y base refrescada antes de publicar: `6173ade56d64051b40586b80386faff79e22a119`. PR #116 seguía en `8b6e48b5cc9243b4884af90b5db876dba09ecc73`. La propuesta añade observación y pruebas, sin duplicar el cambio de cierre de conexiones. No se fusiona ni se despliega.

**NOTA FINAL:** NO_GO para declarar reparada la persistencia. La siguiente prueba necesaria debe vincular un cambio físico concreto con el proceso o transferencia responsable, en el entorno afectado y con el diario fuera del área sincronizada. La configuración rsync observada es una hipótesis documentada, no una atribución del incidente.
