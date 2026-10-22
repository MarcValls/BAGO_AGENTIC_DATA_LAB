# Reparación de integridad del controlador ADL

AUTH-001 y B04-AUTH-002 corregidos en el controlador canónico
[teamctl.py](../../../.bago/team/kit/scripts/teamctl.py) y sus contratos.
La candidata Windows verificada es `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`.
La Suite 1.4.2 RC1 BUILD2 coordinó agentes nativos; su identidad no es la identidad ADL.

## Resultado observado

- Once criterios: PASS desde la entrada activa y el wrapper, con datos sintéticos nuevos.
- Revisión independiente: PASS, cero P0/P1 en el alcance corregido; trece grupos reconstruidos y cinco casos propios.
- Regresión completa Windows: 536 PASS, 1 SKIP, cero fallos. El SKIP figura en el XML y no cuenta como PASS.
- Generación README y comprobación posterior: código 0. `--check --skip-tests` recoge casos y verifica render; no vuelve a ejecutar la suite.

Estas cantidades describen ejecuciones distintas de escenarios relacionados; no se suman como pruebas independientes.
Los recibos prueban argv/resultado y observables declarados localmente, no la calidad semántica de cualquier comando, autenticación del host o aislamiento del proceso.

## Reproducir

Instala `requirements-test.txt` en un entorno propio. Desde la raíz:

```text
python -B tests/test_teamctl_integrity.py --candidate . --artifacts <directorio-nuevo-corto>
python -m pytest tests -q
python scripts/generate_dynamic_readme.py
python scripts/generate_dynamic_readme.py --check --skip-tests
```

El [test reproducible](../../../tests/test_teamctl_integrity.py) invoca procesos CLI reales, registra comandos/códigos y conserva controles positivos, negativos y recuperación.
`--candidate` selecciona implementación; `--artifacts` crea misiones nuevas, nunca debe apuntar al runtime compartido.
En Windows usa rutas temporales cortas. En PYTEST_ADDOPTS, usa barras `/` y comillas: las barras `\` sin proteger son interpretadas por el parser y pueden provocar MAX_PATH.
Un symlink ordinario sin privilegio Windows quedó NOT_RUN/1314; la prueba de rechazo de junction/reparse sí se ejecutó.
Python 3.11 aquí solo recibió comprobación sintáctica; su ejecución corresponde a la CI. Otros sistemas/proveedores no se atribuyen a la ejecución Windows.

## Evidencia

[Matriz de aceptación](acceptance-matrix.json), [ejecución activa](active-acceptance.json),
[revisión independiente](independent-review.md), [sus casos propios](independent-cases.json),
[JUnit completo](full-suite.xml), [órdenes finales](final-gates.json),
[cierre de coordinación](mission-closure.json) y [SHA-256](SHA256SUMS.json).

Son copias exactas de evidencias locales identificadas por SHA. Sus rutas originales siguen descritas en los JSON;
esta carpeta proporciona las copias enlazadas. El manifiesto Windows identifica bytes del entorno observado;
las conversiones LF/CRLF de Git pueden cambiar la identidad de otra instalación. Cada ejecución calcula su propia identidad y no hereda un PASS de otros bytes.

Los históricos permanecen legibles como LEGACY_UNVERIFIED y no se convierten en pruebas actuales mediante identidades o recibos inventados.
El protocolo, SOURCE_LOCK y LICENSE conservan procedencia. Los originales y las copias de recuperación permanecen locales.
Los pendientes CSS, ayuda CLI Suite y retención son trabajos independientes.
