# Decision Inspector — estado final

Fecha: 2026-10-08  
Misión: `AGENT_DECISION_INSPECTOR_V1`  
Estado: **VALIDATED** para el gate explícito de la misión (P0=0, P1=0).

## Resultado

La UI de Decision Inspector está integrada en la aplicación React. Presenta la conclusión fuente, evidencia recuperada, cronología LocalTrace y acciones/recibos en vistas navegables. No inventa claims ni relaciones de soporte; señala los datos ausentes. Los recibos solo pueden quedar asociados si su `run_id` explícito coincide con el `run_id` de la ejecución.

La validación local proyectó **15/15 spans** desde LocalTrace a Jaeger y encontró la traza. Jaeger trace ID: `04b58bb123bb6cc94a8cc0d60c7145ae`. LocalTrace ID: `trace-5b385699ffda0529`. La API del inspector respondió `200` y `/api/health` devolvió `ok` en `http://127.0.0.1:8082`.

## Evidencia visual

- [Decision Inspector — resumen](../../output/playwright/decision-inspector-overview.png)
- [Decision Inspector — cronología](../../output/playwright/decision-inspector-trace.png)
- [Decision Inspector — acciones y recibos](../../output/playwright/decision-inspector-actions.png)
- [Jaeger — grafo de la traza local](../../output/playwright/jaeger-localtrace-04b58bb.png)
- [Validación LocalTrace → OTLP → Jaeger](../../evidence/l15_otel_jaeger_live.md)

## Verificación

- `npm run build` en `frontend`: **PASS**, compilación TypeScript y Vite, 124 módulos.
- Integración Decision Inspector: **5/5 PASS**, incluidos recibos de otro run con IDs coincidentes y recibos sin `run_id`.
- Verificación independiente W11/W14: **0 P0, 0 P1 abiertos**. W11 detectó un P1 de asociación de recibos; W13 lo corrigió y W14 confirmó el cierre con pruebas adversariales y controles positivos.
- `python .bago/team/kit/scripts/teamctl.py verify`: **PASS** para todos los handoffs de la misión.
- `git diff --check`: **PASS**.

## Límites y pendientes

- No hay `claim_id` estructurados ni vínculos claim→evidencia en la ejecución actual. La UI informa que no están disponibles; no deriva claims del texto.
- La UI no dispone de correlación directa con el ID de Jaeger. La evidencia de Jaeger acredita la proyección backend de LocalTrace, no un enlace desde el inspector.
- `AWS live` y `remote collector`: `NOT_RUN`.
- Revisión manual de teclado/lector de pantalla y revisión píxel a píxel de capturas: `NOT_RUN` (P2 no bloqueante).
- La igualdad del `run_id` es identidad aportada por la fuente, no atestación criptográfica del origen del recibo.

## Índice de handoffs

W01–W14 tienen handoffs validados; W12 cierra la misión. Informes independientes: [W11](verification/W11_INDEPENDENT_VERIFICATION.md), [W13](verification/W13_RECEIPT_RUN_BINDING.md), [W14](verification/W14_INDEPENDENT_RECEIPT_VERIFICATION.md).
