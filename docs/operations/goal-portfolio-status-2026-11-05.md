# BAGO5 ADL: estado de la cartera de goals

**Fecha de corte:** 2026-11-05, 11:28 UTC; revisión local posterior a la fusión de la PR #123.

Este es un inventario de resoluciones de expedientes. Un cierre tiene el alcance y candidato de su revisión; no certifica el estado global del producto. La lista puede cambiar cuando aparezca evidencia posterior.

| Resultado de la revisión | Expedientes |
| --- | ---: |
| `CLOSED_ACCEPTED` | 22 |
| `BLOCKED` | 36 |
| `SUPERSEDED_ACCEPTED` | 1 |
| `NO_VALID_RESOLUTION` | 1 |
| **Total** | **60** |

La instantánea local del adaptador tiene SHA-256 `358c404fed6a91d7401fb3476ee619d6fc7348c02dd4927bff76af5fa508224a`. No se publica el índice completo porque contiene rutas locales. Los resultados se basan en recibos TaskStore y no en las etiquetas declaradas de los expedientes; el escaneo no es una instantánea atómica.

La instantánea anterior contabilizaba el goal de exportación y verificación global como cerrado. Una revisión posterior lo mantiene bloqueado: existe una suite satisfactoria con un módulo de pruebas sustituido temporalmente, pero no acredita la suite del árbol final integrado. La evidencia anterior se conserva.

## Resoluciones por expediente

### CLOSED_ACCEPTED

- `ADL-AGENT-EVALUATION-LAB-001`
- `adl-cases-20261022`
- `ADL-EXTERNAL-LIVE-VALIDATION-20261017`
- `adl-ui-standard-pack-001`
- `bago5-chat-cognition`
- `contacts-independent-review-20261023`
- `contacts-repair-review-20261023`
- `CR-GEX-001`
- `docker-independent-review-20261023`
- `docker-live-edit-review-20261023`
- `docker-runtime-final-20261023`
- `duplicate-responsibility-audit-20261020`
- `eval-equal-height-20261020`
- `functional-reuse-20261023`
- `github-update-20261022`
- `L1-GOVERNED-EXECUTION-EVIDENCE-001`
- `model-assignments-20261020`
- `provider-cognition-repair`
- `provider-status-line-20261020`
- `square-color-ui-20261020`
- `teamctl-p1-repair-20261022`
- `workspace-compact-20261020`

### BLOCKED

- `ADL-AGENT-RUN-GOVERNED-001`
- `ADL-BER-INTEGRATION-001`
- `ADL-CAPABILITY-MANAGER-001`
- `adl-chat-semantic-navigation-001`
- `ADL-CHAT-UI-MODERNIZATION-001`
- `ADL-CONVERSATION-LIBRARY-001`
- `ADL-EXPORT-CI-AND-FULL-VERIFICATION-20261017`
- `adl-external-connections-20261020`
- `ADL-FRONTEND-AUDITOR-JAEGER-001`
- `ADL-OLLAMA-SPIRAL-001`
- `ADL-ONE-SHOT-SIGNAL-AGENT-SPIRAL-001`
- `ADL-P1-02-REAL-AUDIT-SPIRAL-001`
- `ADL-PROVIDER-REGISTRATION-001`
- `adl-seven-verticals-20261020`
- `agent-saved-tasks-20261020`
- `brave-browser-mcp-20261020`
- `chat-run-settings`
- `close-fronts-20261023`
- `context-unification`
- `context-viewer-20261020`
- `crit-adl-skills-001-retest-1`
- `directory-code-duplicate-scan`
- `integrated-services-20261023`
- `jaeger-via-adl-20261024`
- `L1-GOVERNED-EXECUTION-COMPLETION-001`
- `model-footer-20261020`
- `one-command-demo-v1`
- `openmetadata-lineage-28860`
- `portfolio-demo-v1`
- `rc4-goals-repair-testbank-20261102`
- `readme-clarity-20261022`
- `readme-corporate-20261022`
- `readme-trust-audit-20261015`
- `task-frictionless-flow-20261101`
- `user-demand-video-20261101`
- `whatsapp-communications-20261022`

### SUPERSEDED_ACCEPTED

- `adl-chat-functions-and-copy-001`

### NO_VALID_RESOLUTION

- `operational-continuity-governance-20261031`

## Trabajo en curso y límites

- [PR #119](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/119) fusionada: mantiene desactivados el generador y las pruebas README heredados. La revisión de README en GitHub sigue detenida.
- Al corte, la [PR #120](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/120) estaba en borrador: comprobación del listener de Brave; el recorrido completo de navegación y recarga figuraba `NOT_RUN`.
- Al corte, la [PR #122](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/pull/122) estaba en borrador: lanzador de instancia única; la CI de esa revisión seguía en curso y la apertura desde el lanzador y la entrada humana del PID figuraban `NOT_RUN`.
- `CR-GEX-001` identifica tanto un goal de contrato como una solicitud distinta de cambio de canon. El cierre del goal es solo de especificación y no aprueba automáticamente la solicitud homónima ni habilita Agent Runner.
- El checkout local contiene cambios aún no conciliados con GitHub; ni esta página ni el estado de `main` demuestran que todos estén publicados.
- La aceptación visual es solo de escritorio. Las revisiones móviles siguen aplazadas.
- Se respetan los controles STOP específicos de continuidad y de grabación.

El índice y las revisiones originales se conservan en el entorno de trabajo. Esta página no concede permisos ni sustituye los criterios de aceptación de cada expediente.
