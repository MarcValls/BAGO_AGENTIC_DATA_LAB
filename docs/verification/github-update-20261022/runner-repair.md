# S02 — propuesta revisable de alcance frontend

## Estado

PREPARED; comprobaciones locales EXECUTED/VERIFIED con alcance descrito debajo.
No se aplicó a archivos activos ni se publicó. Revisión independiente y puertas finales pendientes.
El predecesor `.publication-scope` y scope-review permanecen conservados.
`manifest.json` fija los seis destinos, sus fuentes propuestas, hashes y hashes previos.
No se propone ni aplica cambio de adapter/UI/contrato canónico. package-lock permanece idéntico.

## Propiedad de cada batería

- `npm test`: `vitest run`, sin filtro posicional. vitest.config incluye exclusivamente
  tests/**/*.test.tsx: 14 archivos,127 pruebas. El shim Vite solo permite revisar el archivo
  en su subdirectorio; no se instala sobre el vite.config.ts existente.
- `test:contracts`: node --test tests/contracts/node-contracts.test.mjs. Wrapper Vite middleware/SSR
  carga los tres TS existentes (action,evidence,trace), que utilizan node:test. Su suite describe
  asíncrona registra todos antes de ejecutar el after que cierra el servidor. No mezcla Vitest/node:test.
- `test:ui`: lista explícita de los ocho MJS existentes;49 pruebas. expected-tests.json enumera
  todos los archivos y sus hashes activos. El wrapper nuevo no entra en tests/ui.
- CI completa se propone desde bytes activos y solo añade npm run test:contracts. Los pasos
  redundantes previos se conservan para minimizar el cambio; no se atribuye deduplicación CI.

## Fallos expuestos y decisión de autoridad

Primer intento: TSX14/127PASS; wrapper cerraba SSR entre imports y expuso además dos assertions
action antiguas. Se conserva íntegro en scope2-build/attempt-1. Segundo intento corrige lifecycle:
13 contratos ejecutados,9PASS/4FAIL; evidencia4PASS, action2FAIL y trace2FAIL.

La propuesta inicial de cambiar agentRun a unknown no se adopta: el adapter src/adapters/action
y su mirror frontend tienen bytes idénticos, y el test canónico tests/contracts/action/action.test.ts
exige missing cuando existe request_id sin candidato de recibo. Cambiar solo el mirror habría
introducido una divergencia semántica. action.test.proposed conserva sus cinco casos, alinea
dos expectativas con ese canónico y añade fronteras: sin identidad alguna continúa unknown;
SUCCESS declarado sin recibo sigue unverified. No cambia la puerta de éxito ni autorización.

Trace test antiguo importa LocalTraceRecord inexistente, usa correlation singular y asume
request_id como toolCallId, además de campos claimState/actionState/jaegerCorrelation retirados.
El contrato/documento canónico exige TraceSource, correlations plural y IDs separados.
trace.test.proposed migra sus cuatro casos, preserva chronology/causality, huecos, duplicados,
ERROR y redacción, y exige requestId=req-1 con toolCallId ausente. Se conservan claim/action
explícitos y ausencia de IDs no suministrados. No se cambia adapter ni contrato para hacer pasar
un test antiguo. authority-sources.json registra las fuentes exactas usadas en esta decisión.

Skills aplicadas por asignación: governance-action-engineer y trace-observability-engineer.
Se preservan separación de fases y correlación explícita; no se crea autoridad de ejecución.

## Prueba diferencial final

scope2-build/attempt-3 conserva argv,cwd,exit y logs SHA-256:

| Entrada | Bytes usados | Resultado |
|---|---|---|
| node --test wrapper limpio | Tests activos sin modificar | 13 ejecutados,9PASS/4FAIL,exit1 esperado |
| node --test wrapper de revisión | Solo módulos de test action/trace propuestos | 13PASS,0FAIL,exit0 |
| Vitest run --config propuesta sin filtros | Todos los14TSX activos | 127PASS,exit0 |
| node --test lista explícita8MJS | Todos los MJS UI activos | 49PASS,exit0 |

El loader de revisión reemplaza únicamente bytes de los dos módulos de test bajo su ID original,
conservando imports relativos hacia la fuente real. No sustituye adapters, contratos ni assertions
por resultados prefabricados. Loader y wrapper patched son artefactos de revisión, no destinos.
La configuración instalada usará wrapper limpio y tests migrados; ese recorrido exacto todavía
requiere revisión independiente/integración y repetición npm de la raíz. El comprobador de sellado
también exige los recuentos y cero skipped/cancelled; no interpreta un exit1 genérico como prueba.

Los hashes de package/config/CI/src/tests activos coinciden antes/después de las ejecuciones.
No se ejecutó build ni publicación desde esta entrega. README de producto no se editó/generó;
su cierre corresponde al coordinador. Los checks prueban contratos/UI simulados locales, sin
providers, BER real, permisos de ejecución ni servicios externos conectados.
