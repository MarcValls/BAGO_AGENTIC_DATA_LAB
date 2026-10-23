# Pendientes separados de esta candidata —24 de octubre de2026

| ID | Estado y alcance | Dependencia y criterio de cierre |
|---|---|---|
| PUB-PENDING-001 | **PROPOSED**: jerarquía global del menú según autoridad y permisos | Definir el contrato de autoridad, relacionar cada destino con la operación real y verificar los casos permitidos/denegados. Esta candidata sólo incorpora los tres destinos de Comunicaciones |
| PUB-PENDING-002 | **PROPOSED**: registro de capacidades vinculado al workspace efectivo | El coordinador comunicó un diagnóstico de lectura sobre una lista fija de seis capacidades y una resolución de workspace incorrecta. Requiere reproducirlo con identidad de instancia/raíz, definir la fuente autorizada del registro y probar aislamiento, cambio de workspace y límites. No se cambia ese recorrido en esta publicación |
| PUB-PENDING-003 | **PROPOSED**: historial filtrable por entidad | Faltan eventos persistidos propios de contactos y otras entidades, contrato de identidad/operación/fecha/recibo y consumidores reales. No se inventan filtros ni eventos históricos |
| PUB-PENDING-004 | **NOT_RUN**: CI de esta publicación y efectos externos | Ejecutar CI sobre commit/tree identificados. WhatsApp QR/envío, proveedores y otras operaciones externas requieren sus datos, autorización y entorno específicos |

## P2 aceptados para conservar los bytes RC10

La inspección de `git diff --check` encontró una línea vacía adicional al final de tres archivos: `AgentTaskForm.tsx`, `external-connections.test.tsx` y `governed-fixture.test.tsx`. El coordinador ordenó conservarlas para mantener identidad con RC10. No afectan al comportamiento declarado; quedan visibles para la revisión independiente y no se presentan como una corrección realizada.

La misión previa de Inspector permanece **PAUSED** y el objetivo de pruebas empresariales conserva su continuidad independiente. Este snapshot no los reanuda ni los declara completados.

## PUB-PENDING-002: admisión de capacidades y herramientas

Diagnóstico de lectura24-10-2026: la lista estática de seis capacidades no coincide con los cinco IDs heredados de TOOL_OPTIONS y AGENT_TOOL_ALLOWLIST (`bedrock.converse`, `mcp.execute`, `ontology.query`, `retrieval.search`, `sandbox.run`). La configuración de perfil y las herramientas reales del bucle de chat son contratos diferentes. El chat utiliza herramientas como `read_workspace_file`, escaneo de código, `public_web_read` y `propose_workspace_write` mediante autorizaciones por turno; seleccionar un ID del perfil no demuestra que se admita ni ejecute en ese bucle.

El coordinador observó además seis referencias de fuente no resueltas porque se estaba usando la raíz del workspace. Pendiente: reproducir con identidad de instancia/raíz, unificar registro y resolución de fuentes, y demostrar perfil→admisión→ejecución→recibo mediante casos permitidos y denegados. No se han modificado fuentes para este hallazgo. El runner genérico conserva su estado de no disponible cuando no existe un ejecutor real; no se presenta como una capacidad ejecutada.

Este hallazgo impide afirmar validación completa del sistema o efectividad de asignaciones de herramientas. La presente preparación es un snapshot revisable de servicios y cambios comprobados, para PR draft; no promociona toda la Suite como validada.

## PUB-PENDING-005: orden del entorno de CI antes de publicación

El workflow base instala Node/npmci después de pytest. Los nueve casos DOM observados requieren jsdom durante pytest, por lo que ese orden no prepara el entorno a tiempo. La corrección local crea una dependencia ignorada antes de ejecutar pruebas; no arregla el workflow remoto. El coordinador tramitará un sucesor finito para mover únicamente los dos pasos existentes de Node/npmci antes de pytest, con revisión independiente estática y sin atribuir una ejecución de CI hosted. Es un bloqueo previo al push hasta revisar esa corrección. PP01 no modifica el workflow ni cambia fuentes de aplicación.
