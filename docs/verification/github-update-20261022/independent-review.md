# S02 — revisión independiente de ownership y migración de dos tests

**PASS sobre los seis archivos propuestos**, P0=0/P1=0 en este alcance.
Suite ejecutó `review`, recibo `f23310592c4846228faae5612df1a416`, código0.
No se aplicaron cambios activos, no se cerró misión y no se publicó.
S01 FAIL permanece conservado: sus bytes/resultados no se reutilizan como PASS.

## Identidad y superficies

Se revalidaron todas las entradas congeladas, los seis source/frozen SHA del
MANIFEST, sus hashes activos previos, cada salida sellada del constructor y las
12 fuentes de autoridad. El snapshot antes/después confirma idénticos src/tests
frontend, package, CI, configuración propuesta y package-lock. También se
revalidaron entradas y fuentes canónicas al finalizar. `manifest.json` conserva
los hashes, paths y comandos. Las seis superficies propuestas son config,
wrapper Node, package, CI y tests action/trace; no cambia adapter, UI o contrato.

## Ownership y ejecución sin filtros

| Batería | Comprobación independiente | Resultado |
|---|---|---|
| Vitest TSX | `run --config <propuesta> --maxWorkers=2`, sin argumentos de archivos; reporter JSON permite confrontar lista real con expected | Exactamente 14 archivos,127 PASS,0 failed/pending; ninguna copia privada |
| Contratos Node TS | Wrapper propuesto con ViteSSR y sustitución exclusiva de los dos módulos de test bajo su ID original | 13 PASS,0 fail/skipped/cancelled |
| UI Node MJS | Lista de ocho archivos propuesta en package y expected, con fuentes activas | 49 PASS,0 fail/skipped/cancelled |
| Controles propios | Cinco casos nuevos usando adapters reales cargados por ViteSSR | 5 PASS,0 fail/skipped/cancelled |

Las listas esperadas coinciden exactamente con los TSX, TS node:test y MJS
presentes en `frontend/tests`. Ningún test de producto queda sin propietario:
Vitest toma TSX y el wrapper Node carga los tres TS. package conserva dependencias
y demás campos/scripts; cambia npm test a `vitest run`, publica test:contracts y
lista los ocho MJS en test:ui. CI se compara como texto contra activo: únicamente
añade el paso `npm run test:contracts`; los pasos previos permanecen intactos.
La configuración conserva el Vite/React existente mediante mergeConfig.

`commands.json` conserva argv/cwd/exit y hashes de stdout/stderr. Los cuatro
comandos terminaron0 y sus stderr están vacíos. `vitest.json` enumera los archivos
descubiertos realmente; no se limitó la búsqueda por nombres posicionales.

El loader independiente solo reemplaza los bytes de
`frontend/tests/contracts/action/action.test.ts` y trace equivalente por sus
versiones congeladas. No reemplaza imports de adapters/contratos, assertions ni
resultados. `loader-hits.json` exige exactamente esos dos IDs. El wrapper conserva
el describe asíncrono y after: importa los tres módulos antes de cerrar Vite.
El fixture de revisión resuelve Vite por URL absoluta porque vive bajo la raíz
de evidencia; la instalación propuesta usa el import normal y requiere la prueba
final desde npm tras aplicar. No se presenta el loader como producto instalado.

## Migración action: cambio conforme al canon

El adapter canónico y mirror frontend tienen SHA idéntico
`f3fd1f4c0356e25fe23444d72beaa7e84d979ddade9bcf5f4fa5d04e94ee87f6`.
El test raíz canónico exige `missing` cuando existe request_id sin candidato de
recibo; la fuente aplica ese mismo predicado. El test frontend anterior esperaba
`unknown` en ese caso, contradiciendo canon y fuente efectiva. Corregir esas dos
expectativas no relaja la puerta de éxito. Se conservan cinco casos originales:
separación de fases, expiración, rechazo/fallo con evidencia, recibo ausente o
mismatch y ausencia de IDs. Se añaden aserciones de frontera dentro del último.

Controles nuevos ejecutados directamente sobre el adapter:

- Propuesta sin identidad: id ausente, autorización/ejecución/recibo unknown.
- Request conocido y called SUCCESS sin recibo: missing y unverified, aun con
  decisión ALLOW; autorización no acredita ejecución.
- Request, permit y effect mismatched, cada uno por separado: mismatch y
  ejecución unverified. Ninguno convierte SUCCESS declarado en éxito verificado.

El test raíz más amplio y documentos canónicos no se editaron. No se reduce su
cobertura ni se atribuye autenticación a la proyección de recibos.

## Migración trace: API actual e identidad explícita

Contrato canónico y mirror coinciden; el adapter solo copia IDs explícitos de
attributes. Documento `decision-trace-v1.md` exige separarlos y prohíbe convertir
request/proposal/evidence refs en otras identidades. TraceSource y correlations
plural son los tipos/campos efectivos. LocalTraceRecord, correlation singular y
claimState/actionState/jaegerCorrelation del test antiguo no pertenecen a esa API.

Los cuatro casos preservan orden cronológico frente a causalidad, sequence gap,
parent ausente, ERROR, redacción, duplicados retenidos y claim/action explícitos.
Los controles propios comprueban además requestId sin toolCallId inferido,
requestId y toolCallId distintos cuando ambos se suministran, event/run IDs
conservados y execution/receipt/claim/action explícitos. ERROR y `[REDACTED]`
permanecen intactos; una evidence ref no produce receiptId cuando falta atributo.
No se cambia implementación para satisfacer expectativas viejas.

Se aplicaron por asignación las reglas de governance-action-engineer y
trace-observability-engineer; esta revisión no implementa las superficies que
verifica. No se invocó BER real, proveedor, navegador ni servicio externo.

## Entrega y límites

Resultado SHA-256:
`cd1062ffde4dc50c17c0a87981acdee21d929d6580d7cd06c6c8097ac96e53f0`.
PASS solo para propuesta congelada y pruebas locales descritas. Aplicación de los
seis destinos, ejecución de wrapper/npm/CI sobre instalación efectiva, build,
README y publicación corresponden al coordinador. No se reabre la reparación
P1 del controlador previamente cerrada ni se declara cierre de GitHub.
