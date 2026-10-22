# README corporativo BAGO — verificación final local

**PASS documental.** Candidata basada en `2d521170fdf651da482b5bf9d5b229a41412a8d2`.
README SHA-256: `e2562629dd142f9e6c8cf050d6852058e4cf88f17903c2f91891c1c8a8d337fc`.

| Comprobación ejecutada | Resultado | Evidencia |
|---|---|---|
| `python scripts/generate_dynamic_readme.py` | 553 PASS, 1 SKIP, 0 FAIL, 0 ERROR | [XML](windows-full-suite.xml), [log](generation.log) |
| `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS de reproducibilidad; suite NOT_RUN en esta segunda orden | [log](render-check.log) |
| Revisión independiente de documentación | PASS: 14 secciones, enlaces y evidencia | [informe](independent-review.md) |

Las dos órdenes obligatorias terminaron con código cero. La primera ejecutó
la suite; la segunda solo recogió casos y comparó el README. No se suman sus
conteos. Windows y Python 3.14; entorno, comandos y hashes del alcance en
[windows-validation.json](windows-validation.json). El SKIP corresponde al
privilegio de creación de enlaces simbólicos en Windows, según el XML.

La CI heredada del commit 64a88fbc se conserva [por separado](../ci-summary.json).
La documentación de esta candidata no cambia las fuentes frontend ni convierte
esa CI anterior en una nueva ejecución. La demostración visual sí usó un proveedor
real en el runtime identificado en [su resultado](../demo/RESULT.json).

## Demostración y hallazgos

Nuevo agente, nuevas conversaciones y workspace sintético: lectura autorizada,
respuesta de GPT-6-Luna y citas contrastadas. [Capturas y pasos](../../../assets/readme-20261022/README.md).

**CHAT-DEMO-001 permanece FAIL:** Inspect muestra otra traza Bruma, no la del chat
nuevo. No se reparó ese componente en este trabajo de documentación. Para cerrarlo,
la navegación debe mostrar el mismo trace_id y la misma lectura de la conversación.
No se demostraron pagos, ejecución genérica de herramientas ni aprendizaje continuo.

## Conservación

Los originales y las capturas históricas se conservan. Los cambios locales del
checkout principal no forman parte de esta candidata de documentación. Las pruebas
se ejecutaron en el worktree y con configuración, conversación y workspace aislados.
Los hashes de los archivos congelados y los logs permiten contrastar esta ejecución.
El manifiesto SHA no se incluye a sí mismo y corresponde a estos bytes Windows.
