# ADL — Arquitectura visual del chat orquestador y foco contextual

**Versión:** Visual 001 · **Fecha:** 18-10-2026 · **Estado:** PROPUESTO / NO VERIFICADO

> **Tesis:** El chat permanece general; el orquestador coordina trabajos y agentes independientes; el foco dirige la referencia del usuario sin cambiar la identidad de la conversación ni conceder autoridad.

| Propiedad | Regla |
|---|---|
| Chat principal | Una interfaz conversacional permanente con ADL. |
| Orquestador | Mantiene la coordinación y supervisión global. |
| Foco | Referente prioritario; puede ser una entidad, ejecución o trabajo compuesto. |
| Agentes | Trabajan en segundo plano con contextos y límites propios. |
| Componentes | Misma ficha/editor en chat y pantallas especializadas; un estado compartido. |
| Ejecución | Solo a través de controles de autorización y despacho gobernado. |
| ADL | Contrasta resultados y evidencias de manera independiente. |

## 1. Mapa estructural

![Mapa arquitectónico](ADL_ARQUITECTURA_VISUAL_001.svg)

## 2. Responsabilidades y límites

| Componente | Responsabilidad | No debe hacer |
|---|---|---|
| Chat general | Conversación única; integra componentes, avisos y resultados. | No cambia de identidad por usar agentes. |
| Orquestador | Interpreta, coordina trabajos, consulta capacidades y resume con procedencia. | No convierte propuestas en permisos. |
| Resolutor de foco | Determina el referente pertinente de cada intervención. | No obliga a una vinculación permanente. |
| Servicio de contexto | Recupera selectivamente datos y relaciones autorizados. | Conocer una ruta o entidad no concede acceso. |
| Componentes compartidos | Misma ficha/editor en chat y pantallas especializadas. | No duplica configuración, borradores ni validaciones. |
| Dominio y estado | Identidad y persistencia de agentes, proyectos y configuraciones. | No depende de la superficie que inició el cambio. |
| Registro de trabajos | Relaciona tareas, agentes, ejecuciones y su estado. | No equivale al estado de la conversación. |
| Ejecución gobernada | Fija objetivo, verifica política y autoriza el despacho. | No interpreta el foco como autorización. |
| Evaluación ADL | Contrasta trazas, pruebas y resultados con evidencias. | No confunde afirmaciones de agentes con verificación. |

## 3. Modelo de foco

![Separación de foco y autoridad](ADL_FOCO_CONTEXTUAL_001.svg)

| Concepto | Ejemplo | Regla |
|---|---|---|
| Identidad del chat | ADL · Orquestador | Permanece general durante toda la sesión. |
| Mención | «He hablado del Inspector» | No implica seleccionar, enfocar ni consultar datos. |
| Selección visual | «He abierto la ficha RUN-024» | No fija por sí sola el referente conversacional. |
| Foco | «Ahora nos centramos en RUN-024» | Ayuda a resolver referencias elípticas; es reversible. |
| Destino de acción | «Ejecuta pruebas sobre el agente X» | Queda vinculado a la solicitud antes de ejecutarse. |
| Autoridad | Grant / aprobación / política | Es independiente de la identidad y del foco. |

**Prioridad para resolver el referente:** objetivo explícito del mensaje actual → objetivo de una acción gráfica inequívoca → foco fijado si es compatible → referencia conversacional reciente si es inequívoca. Ante ambigüedad relevante para una acción, pedir desambiguación. Una nueva intención explícita prevalece sobre el foco.

## 4. Recorrido operativo

![Recorrido operativo y trabajos paralelos](ADL_RECORRIDO_OPERATIVO_001.svg)

**Negociar → Editar ficha única → Validar → Crear agente → Delegar mediante autorización → Ejecutar en segundo plano → Evaluar con evidencias.**

El foco puede cambiar sin interrumpir el trabajo de otros agentes. Una ejecución autorizada mantiene su destinatario aunque cambie el foco del usuario.

## 5. Contratos mínimos

| ID | Contrato | Alcance |
|---|---|---|
| C-01 | Identidad y relaciones | Conversación, agente, proyecto, tarea, ejecución, evidencia. |
| C-02 | Foco contextual | Prioridad, explicitud, ambigüedad, reversión y concurrencia. |
| C-03 | Componente y borrador común | Edición bidireccional, revisión y persistencia validada. |
| C-04 | Delegación gobernada | Solicitud tipada, objetivo fijo, autorización, ejecución, recibos. |
| C-05 | Contexto y seguridad | Recuperación selectiva; permisos por fuente e intención. |
| C-06 | Observabilidad y evidencia | Vínculos entre trabajos, trazas, pruebas y dictámenes. |

## 6. Invariantes

- El chat principal sigue perteneciendo a ADL, nunca a un agente de segundo plano.
- El foco es una referencia interpretativa, no una frontera de permisos.
- Una instrucción explícita nueva prevalece sobre el foco anterior.
- Una acción con efectos fija su destinatario antes de pedir autorización.
- El trabajo de agentes continúa aunque cambie el foco del usuario.
- Una ficha embebida y una ficha convencional editan el mismo borrador/versionado.
- La evaluación de ADL permanece independiente y también sirve para componentes externos.
- Los resultados se etiquetan PROPUESTO, IMPLEMENTADO o VERIFICADO según su evidencia.

## 7. Primera vertical demostrable

| Paso | Entregable | Criterio |
|---|---|---|
| 01 | Inventario real | Localizar chat, agentes, formularios, autorización, ejecución y evidencias. |
| 02 | Editor común | Insertar la ficha del agente en chat; probar edición bidireccional. |
| 03 | Resolver foco | Permitir foco en agente y ejecución sin alterar conversación general. |
| 04 | Delegación segura | Vincular destinatario y autorizar ejecución antes del despacho. |
| 05 | Concurrencia y evidencia | Mostrar múltiples trabajos, inspección de resultados y pruebas. |
| 06 | Retest diferencial | Comprobar aislamiento, anti-redirección y ausencia de regresiones. |

**Dictamen:** arquitectura PROPUESTA. No se ha inspeccionado el estado actual del repositorio para esta entrega. Antes de cualquier afirmación de IMPLEMENTADO / VERIFICADO se necesitan pruebas y evidencias; no cambiar contratos congelados sin regresión demostrada.
