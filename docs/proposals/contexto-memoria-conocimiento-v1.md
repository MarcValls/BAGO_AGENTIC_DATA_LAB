# Propuesta: módulo de contexto, memoria y conocimiento para el chat orquestador

**Estado:** `PROPOSED` — documento para revisión y auditoría externa  
**Fecha:** 2026-10-19  
**Proyecto:** [BAGO Agentic Data Lab en GitHub](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB)  
**Base revisada:** commit [`f94811f7b186fec36f405403230f2d48d92dfb0c`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/tree/f94811f7b186fec36f405403230f2d48d92dfb0c)

## 1. Resumen ejecutivo

Se propone añadir al backend un módulo lógico de **Contexto y Memoria** que permita al chat orquestador recuperar información pertinente desde fuentes conectadas y entregar al razonamiento un paquete de contexto acotado, trazable y adecuado al ámbito activo.

La propuesta distingue cuatro cosas que no deben confundirse:

1. **Fuentes:** sistemas y artefactos originales, como el workspace, Git, conversaciones, documentos o recursos MCP.
2. **Memoria:** continuidad seleccionada y gobernada: preferencias, decisiones aceptadas y estado relevante de un proyecto o tarea.
3. **Conocimiento:** afirmaciones, entidades y relaciones que conservan evidencia, procedencia y vigencia.
4. **Contexto del turno:** selección temporal de elementos autorizados y pertinentes que recibe el orquestador para responder o decidir.

El módulo debería comenzar dentro del backend existente, con límites e interfaces propios. Docker puede empaquetarlo o alojar dependencias cuando exista una necesidad operativa concreta; no define estas responsabilidades ni es requisito para validar el diseño.

## 2. Necesidad y resultado buscado

El usuario formula una petición normal en el chat. El orquestador identifica el ámbito pertinente, consulta las fuentes permitidas, distingue datos actuales de decisiones aceptadas y devuelve una respuesta apoyada en referencias verificables. Si falta autorización, la fuente no está disponible o hay conflicto entre versiones, el sistema lo hace visible en vez de completar el hueco como si fuera un hecho.

El usuario no debería tener que aprender nombres de comandos para activar la recuperación. La configuración de workspace y fuentes corresponde a **Workspace**; la solicitud y el resultado permanecen en el **chat orquestador**.

## 3. Modelo conceptual propuesto

| Responsabilidad | Contenido y función | No debe convertirse en |
|---|---|---|
| **Fuente** | Contenido original con identidad, ámbito, versión y acceso controlado. | Una verdad validada solo por haberse encontrado. |
| **Memoria** | Continuidad útil, curada y delimitada por ámbito; mantiene ciclo de propuesta, aceptación, sustitución o retirada. | Un volcado indiscriminado de conversaciones o historial Git. |
| **Conocimiento** | Hechos, conceptos y relaciones con procedencia y evidencia asociada. | Texto sin fuente o salida del modelo promovida automáticamente a canon. |
| **Contexto del turno** | Subconjunto temporal seleccionado para una petición, con el motivo y las fuentes de inclusión. | Un almacén persistente ni una autorización para ejecutar acciones. |

Ámbitos iniciales de memoria: `general`, `project`, `workspace` y `conversation/task`. El alcance efectivo debe ser explícito. Una memoria general no se copia automáticamente a un proyecto y una decisión de proyecto no se convierte automáticamente en preferencia global.

## 4. Flujo propuesto

```text
Petición en chat
  → interpretación semántica de intención y ámbito
  → política de fuentes y permisos
  → recuperación de memoria/conocimiento pertinente
  → filtro por autoridad, vigencia, ámbito y evidencia
  → paquete de contexto con procedencia y límites
  → inferencia y decisión
  → autorización separada, si se propone una acción
  → respuesta o ejecución gobernada con recibo
```

Las responsabilidades ontológica, semántica, causal/decisional y procedural consumen o producen información dentro del flujo. No son tipos de almacenamiento:

- **Ontológica:** define entidades, propiedades y relaciones.
- **Semántica:** interpreta la petición y el significado del material recuperado.
- **Causal y decisional:** estima efectos y selecciona una acción candidata.
- **Procedural:** describe cómo realizar una acción ya seleccionada y autorizada.

El aprendizaje procedural debería requerir evidencia de ejecución, resultado verificable y aceptación gobernada. Un rastro de herramienta por sí solo no crea un procedimiento aprobado.

## 5. Encaje con componentes existentes

La propuesta reutiliza componentes observados en el repositorio, sin afirmar que ya implementen toda la capacidad:

- [`workspace_binding.py`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/src/context/workspace_binding.py) vincula el trabajo a identidad y revisión de repositorio/workspace. Puede aportar el ámbito y la identidad de la fuente.
- [`governed_rag.py`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/src/retrieval/governed_rag.py) separa recuperación de generación y ejecución, filtra por metadatos y conserva referencias de evidencia. Puede servir como motor de búsqueda de conocimiento/contexto.
- [`docs/governed_rag.md`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/docs/governed_rag.md) documenta el límite actual: el retriever propone contexto, no llama a proveedores, no ejecuta efectos ni concede permisos.
- [`mcp_adapter.py`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/src/adapters/mcp_adapter.py) gobierna descubrimiento/registro/ejecución de herramientas MCP. La consulta de recursos MCP de solo lectura requeriría definir y verificar un adaptador explícito; no se presume que la interfaz actual ya lo cubra.
- [`ARCHITECTURE.md`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/.bago/canon/ARCHITECTURE.md) contiene el canon arquitectónico consultado para esta revisión.

En el inventario de `src/` revisado para esta propuesta aparecen `src/context/` y `src/retrieval/`; no se encontró un paquete dedicado de memoria duradera con ámbitos, ciclo de aceptación y supersesión. Esta es una observación de alcance de la búsqueda realizada, no una afirmación sobre todo componente externo o runtime instalado.

## 6. Módulo y contratos recomendados

Como primera forma, un módulo interno con límites claros, por ejemplo:

```text
src/context/
  scope.py                 # identidad y ámbito activo
  source_contracts.py      # contratos de fuentes y referencias
  memory_records.py        # registros y estados de memoria
  memory_repository.py     # persistencia/versionado
  context_policy.py        # autoridad, vigencia, permisos y conflictos
  context_assembler.py     # paquete de contexto por turno
  adapters/
    git_source.py
    conversation_source.py
    mcp_resource_source.py # si se implementa y gobierna
```

Los nombres son ilustrativos. Se recomienda no duplicar el retrieval híbrido de `src/retrieval/` ni absorber el binding de workspace. Si el módulo crece, puede dividirse después en paquetes internos, un servidor MCP o un servicio de red.

### Registro mínimo de memoria/conocimiento

Cada elemento recuperable debería poder expresar, como mínimo:

- identificador estable y tipo (`memory`, `fact`, `decision`, `procedure`, `source excerpt`);
- ámbito (`general`, `project`, `workspace`, `conversation/task`);
- contenido o referencia al contenido, evitando duplicar material sensible sin necesidad;
- fuente, URI/ruta lógica, revisión o commit, fecha de observación y huella cuando proceda;
- autoridad, estado (`PROPOSED`, `ACCEPTED`, `SUPERSEDED`, `DEPRECATED`, `INVALID`), vigencia y responsable de aprobación;
- evidencia asociada, motivo de inclusión y relación con elementos en conflicto;
- reglas de acceso y sensibilidad.

Los registros propuestos no deberían participar en respuestas como decisiones aceptadas, salvo que el orquestador los presente explícitamente como propuestas.

## 7. Fuentes iniciales

### Workspace y repositorio Git

Git es una fuente útil de identidad, revisiones y cambios. La recuperación debe ser selectiva: contexto canónico, documentos de decisión y cambios relevantes ligados a commits concretos. El historial completo no equivale a memoria curada. El binding de workspace aporta una base para fijar a qué repositorio y revisión se refiere una consulta.

### MCP

MCP puede conectar servicios externos. Conviene distinguir recursos de lectura y llamadas a herramientas con efectos. La lectura también requiere autorización, identidad de fuente, versión y límites de datos. Descubrir una herramienta no equivale a confiar en su contenido ni a conceder capacidad de ejecución.

### Conversaciones y memoria general

La conversación puede ser una fuente para extraer candidatos a memoria, no una fuente de canon por defecto. Deben conservarse ámbito y procedencia. Las preferencias generales han de mantenerse separadas de decisiones de proyecto y del estado local del workspace.

## 8. Docker: utilidad y frontera

El repositorio ya contiene [`docker-compose.ui.yml`](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/blob/f94811f7b186fec36f405403230f2d48d92dfb0c/docker-compose.ui.yml), que declara el servicio de API/UI y Jaeger opcional. Esto acredita que Docker Compose forma parte de los artefactos del proyecto; no acredita un servicio de memoria.

Docker/Compose puede ser útil para:

- reproducir y empaquetar el runtime del backend;
- ejecutar dependencias separadas, como una base de datos o un servidor MCP;
- aislar conectores con acceso a rutas/secretos delimitados;
- persistir la base mediante volúmenes o mounts y operar servicios juntos.

Docker no aporta por sí mismo el modelo de autoridad, la selección semántica, el ciclo de aprobación, la procedencia ni la política de contexto. Por ello, la recomendación es **definir primero los contratos del módulo y su integración local**. Separarlo como contenedor se justifica si hay consumidores independientes, requisitos de aislamiento/deploy o necesidades operativas medibles. Compose permite configurar y operar servicios coordinados; los volúmenes mantienen datos fuera del ciclo de vida de los contenedores ([Compose](https://docs.docker.com/compose/), [volúmenes](https://docs.docker.com/engine/storage/volumes/)).

En la máquina revisada, `docker --version` respondió `29.8.0`, pero `docker info` no pudo conectar con el motor por denegación de acceso a `npipe:////./pipe/docker_engine`. La disponibilidad operativa del daemon queda `NOT_VERIFIED` en esta revisión.

## 9. Límites de seguridad y gobernanza

1. La recuperación no concede permisos de escritura ni de ejecución.
2. El contexto se filtra por ámbito y autorización antes de ranking semántico.
3. Cada respuesta debe poder distinguir evidencia, inferencia y memoria aceptada.
4. Las fuentes contradictorias se exponen con sus revisiones; no se resuelven silenciosamente por similitud o fecha.
5. La ingesta de fuentes externas permanece aislada de secretos, rutas no seleccionadas y acciones materiales.
6. El usuario puede corregir, retirar o sustituir una memoria; los cambios mantienen historial auditable.
7. Los contenidos de herramientas o recursos MCP son datos no confiables hasta pasar la política de origen y evidencia.
8. El orquestador muestra qué contexto influyó cuando eso afecte una respuesta o decisión relevante.

## 10. Entrega incremental recomendada

1. **Contrato:** especificar `ContextItem`, ámbito, fuente, evidencia, estados, vigencia, conflictos y política de acceso.
2. **Lectura local:** integrar workspace/Git de solo lectura y un pequeño conjunto autorizado de documentos; producir un paquete de contexto con referencias.
3. **Memoria curada:** permitir candidatos, revisión/aceptación, supersesión y recuperación por ámbito.
4. **Chat:** conectar la intención natural del usuario con el ensamblador; mostrar fuentes e incertidumbre en el chat y mantener configuración de fuentes en Workspace.
5. **MCP y servicios externos:** añadir adaptadores uno por uno con permisos y evidencia propios.
6. **Despliegue:** evaluar Docker/Compose cuando existan contratos y una necesidad concreta de servicio, aislamiento o persistencia.

## 11. Criterios para considerar que cumple la función

La propuesta cumpliría su objetivo cuando una revisión pueda verificar que:

- una petición natural recupera material pertinente sin requerir una frase de comando fija;
- la consulta queda limitada al ámbito elegido y no mezcla memoria de otros proyectos;
- cada elemento incluido apunta a su fuente/revisión y declara su estado;
- material obsoleto, inválido o no autorizado no se presenta como conocimiento vigente;
- los conflictos y la incertidumbre llegan al orquestador y se reflejan en la respuesta;
- las propuestas de acciones conservan autorización/ejecución separadas de la recuperación;
- se puede inspeccionar qué elementos formaron el contexto de un turno y por qué;
- existe una evaluación con casos positivos, irrelevantes, contradictorios, obsoletos y de aislamiento entre ámbitos.

Estos son criterios propuestos; no se han implementado ni validado en esta revisión.

## 12. Decisiones solicitadas a la auditoría

1. ¿Es adecuada la frontera entre fuentes, memoria, conocimiento y contexto del turno?
2. ¿Son suficientes los ámbitos propuestos o falta separar otro tipo de continuidad?
3. ¿Qué condiciones deberían hacer que una memoria pase de propuesta a aceptada?
4. ¿Qué evidencia mínima debería exigirse para decisiones y procedimientos?
5. ¿Existe una necesidad real de aislar el módulo en Docker/MCP desde la primera entrega?
6. ¿Qué riesgos de privacidad, contaminación entre ámbitos o recuperación incorrecta no están cubiertos?

## 13. Estado de auditoría y publicación

Este documento describe una propuesta. No representa una decisión canónica aprobada, un módulo implementado ni una validación de calidad funcional.

Los enlaces de código apuntan al commit base indicado en la cabecera. El archivo Markdown se ha creado en el checkout local y todavía no forma parte del historial de GitHub. La publicación del documento requiere incorporar y publicar este archivo mediante el flujo normal del repositorio.
