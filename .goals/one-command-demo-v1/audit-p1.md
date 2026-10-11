# PROMPT 1 — Auditor de cierre (solo lectura)

Fecha de auditoría: 2026-10-02/03 environment (repo snapshot HEAD `e99f4736d2cb18c5ce4920695f7b2547e3e73fbf`).

## 1. Estado actual

- La capacidad compuesta ya existe en `scripts/run_public_e2e_demo.py` y reutiliza fixtures locales, GovernedRAG, OntologyEngine, Bedrock-shaped injected client, sandbox tipado, LocalTrace y LocalTraceEvaluator.
- Ejecución observada: `python scripts/run_public_e2e_demo.py --check` → `status=PASS`, agent `COMPLETED`, 2 retrieval hits, ontology `SUCCESS`, 4 paths, sandbox `SUCCESS`, 15 trace events, evaluation `PASS` score `1.0`; AWS/OpenMetadata live `NOT_RUN`.
- Tests antes de cambios: `149 passed, 5 warnings`.
- CI ejecuta tests, README check, demo `--check`, vector validation, local OpenMetadata + Jaeger checks y compileall.
- Docs actuales indican Python 3.11+, `pip install -r requirements.txt`, no credentials/network/Docker para el public E2E. Windows no tiene ruta propia descrita.
- `demo.py` no existe. No existen `summary.json`, `agent_run.json`, `receipts.json`, `trace.json`, `evaluation.json` en el checkout; el demo imprime solo summary JSON a stdout y `--write-evidence` escribe Markdown.
- `AgentRun`, sandbox receipt, `LocalTrace` y `EvaluationReport` ya tienen `to_dict`; hay serialización reutilizable, sin arquitectura nueva.
- `README.md` es generado y actualmente presenta el portfolio general, no el contrato específico de one-command demo/artifacts.
- `pip check` del Python global local informa un conflicto `litellm` ↔ `click`; ninguno aparece como dependencia directa en `requirements.txt`. Es estado de entorno ajeno, no evidencia de fallo en entorno limpio. Debe comprobarse en clean venv, no modificar deps por conjetura.

## 2. Barra estimada

`████████████████░░░░ 80 %`

Estimación basada en el sistema E2E ya funcional; el empaquetado de un comando, artefactos JSON canónicos, documentación dedicada y evidencia desde clon limpio faltan.

## 3. Blockers reales exhaustivos

### B1 — No existe el entrypoint solicitado

Reproducción: `ls demo.py` → inexistente. El comando público documentado exige conocer `python scripts/run_public_e2e_demo.py --check`; no cumple `python demo.py` ni una sola ejecución que conserve outputs.

### B2 — No se materializan los cinco artefactos del contrato

Reproducción: `find evidence -name '*.json'` → ninguno; `--check` devuelve summary en stdout y `--write-evidence` solo escribe `evidence/public_e2e_demo.md`. La petición explícita requiere summary/agent/receipts/trace/evaluation JSON asociados a una misma run.

### B3 — El CLI existente no falla ante evaluación FAIL como artefacto de cierre

`run_demo()` lanza errores si los gates fallan; no existe output directory ni error receipt persistido. El flujo es adecuado para tests, pero un usuario externo no dispone del contrato de ejecución/error de `python demo.py`. Esto se resolverá solo dentro del wrapper, reutilizando el runner.

### B4 — README/CI no documentan ni gatean el contrato pedido

README contiene comandos L13 y panorama del repo, no `python demo.py`, output paths ni lectura de los cinco artifacts. CI llama el runner existente, no el entrypoint público/artifact contract.

### B5 — Clean-clone Windows y entorno aislado no comprobados

La documentación enumera Python 3.11+ y requirements pero no verifica el comando solicitado en venv limpio ni PowerShell. Blocker de evidencia de publicabilidad hasta reproducir en clon limpio; no hay evidencia actual de fallo de portabilidad.

## 4. Prioridades

- **P0:** ninguno demostrado; el runner público y sus tests funcionan.
- **P1:** B1/B2 (claim principal one-command + five artifacts ausente); B4 (contrato del demo no es encontrable desde README/CI); B5 (falta evidencia clean clone requerida).
- **P2:** mostrar el resultado de forma más breve/bonita, reproducir el video portfolio desde el nuevo demo, limpiar warnings de Python 3.14, resolver el conflicto `pip check` del entorno global — mejoras opcionales/no relacionadas con el claim si venv limpio instala.

## 5. Qué NO debe tocarse

- `src/agent/governed_knowledge_agent.py`, `src/retrieval/governed_rag.py`, `src/metadata/ontology_engine.py`, `src/sandbox/*`, `src/observability/local_trace.py`, `src/evaluation/local_evals.py` salvo regresión demostrada.
- adapters/cloud live, Jaeger/OpenMetadata/Docker configs, `STATE.md`, portfolio tag anterior.
- No introducir base de datos, nuevos agentes, framework CLI, LLM remoto ni subsistema de artifact store.

## 6. Archivos que necesitan cambios (si implementación autorizada por secuencia)

- Nuevo `demo.py` raíz: thin entrypoint, invoca `scripts.run_public_e2e_demo.run_demo`, serializa resultados existentes.
- `scripts/run_public_e2e_demo.py`: solo si extraer serialización compartida evita duplicar el runner; preferir wrapper puro en demo.py y ningún cambio al runner si alcanza.
- Nuevo test `tests/test_one_command_demo.py`: verifica artifacts, enlaces/IDs, errores y salida de comando.
- `.github/workflows/ci.yml`: invocar `python demo.py` y comprobar artefactos/contrato, manteniendo gates previos.
- Fuente de README `docs/readme_manifest.json` + `scripts/generate_dynamic_readme.py` (o docs enlazadas por el generador), porque README no se edita manualmente.

## 7. Archivos que solo necesitan documentación

- `docs/public_e2e_demo.md` o nueva página focalizada: comando Windows/Unix, instalación, directorio de outputs, significado de cada JSON, input/output ejemplo, límites/errores y walkthrough.
- README generado: problema, flujo solicitado, quickstart, ejemplo, artifacts y limitaciones, dentro de menos de 3 min de lectura.
- Release notes v1.0 al llegar a freeze.

## 8. Secuencia mínima a 100 %

1. Añadir root `demo.py` como adaptador fino sobre `run_demo()` y `to_dict()` existentes; guardar los cinco JSON en un directorio de salida documentado, con escritura atómica si simple y pruebas lo justifican.
2. Mantener summary stdout/exit code útil; un único run ID/trace ID enlaza agent, receipt, trace y evaluation. Sin credenciales, Docker ni red.
3. Test de integración de comando que valida cinco archivos y consistencia IDs; test fail-path sin efectos externos.
4. Documentar instalación/comando, outputs y ejemplo (Windows PowerShell y shell POSIX).
5. Incluir el comando y artifact contract en README generado y CI.
6. Ejecutar clean clone + venv Python 3.11; ejecutar `python demo.py`; inspeccionar artifacts.
7. Suite completa, README check, CI workflow/static validation.
8. Auditor de release independiente; freeze/tag solo con findings P0/P1 cero.

## 9. Criterios objetivos de DONE

- Clon temporal limpio: seguir únicamente repo docs, crear venv e instalar requirements.
- `python demo.py` termina 0 sin env vars ni servicios externos.
- Directorio de outputs declarado contiene los cinco JSON válidos.
- Los cinco vienen del mismo run; agent run ID = trace run ID; evaluation trace ID = trace ID; receipts referenciados por trace; summary indica PASS y score 1.0 (para fixture actual).
- Repetir comando no necesita editar código; los IDs/timestamps pueden variar y la doc lo explica, mientras los resultados semánticos permanecen iguales.
- README generado/check pasa, CI incluye demo, tests cubren contrato, suite completa pasa.
- Limits `AWS live NOT_RUN`, `OpenMetadata live NOT_RUN`, fixture model/no transport/cost 0 remain explicit.
- Release candidate hash/tag/notes registrados y crítico independiente reporta P0=0 y P1=0.

## 10. Veredicto

`NOT_READY_TO_CLOSE`

No se implementó nada durante auditoría. B1/B2 impiden el claim objetivo y la reproducción clean-clone solicitada todavía no está demostrada.
