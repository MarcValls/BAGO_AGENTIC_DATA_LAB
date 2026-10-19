# BAGO — Pantalla de Proveedores y Modelos

**Objetivo:** centralizar el registro de proveedores de IA, la configuración de conexiones, la selección de modelos activos y la asignación de modelos a las distintas funciones de BAGO.

La pantalla debe permitir administrar todo esto sin tener que modificar archivos de configuración manualmente.

Visualmente seguiría el estilo de Windows: fondo claro, paneles independientes, bordes finos, esquinas de unos 4 px y pocos elementos decorativos.

## 1. Representación gráfica general

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ BAGO                                      PROVEEDORES Y MODELOS                         Buscar...    ⚙   │
├───────────────────┬──────────────────────────────────────────────────────────────────────────────────────┤
│                   │                                                                                      │
│  INICIO           │  Proveedores y Modelos                                          [+ Añadir proveedor] │
│                   │  Gestiona conexiones, modelos disponibles y configuración de uso.                    │
│  Chat             │                                                                                      │
│  Agentes          │  ┌──────────────────┬──────────────────┬──────────────────┬──────────────────────┐ │
│  Herramientas     │  │ 7 tipos integrados    │ modelos por cargar      │ estado por verificar       │ uso por función   │ │
│  Proyectos        │  │ conexión pendiente     │ modelos dinámicos │ sin estado asumido  │ Por función         │ │
│  Datos            │  └──────────────────┴──────────────────┴──────────────────┴──────────────────────┘ │
│  RAG              │                                                                                      │
│  Ejecución        │  ┌──────────────────────┬────────────────────────────────┬────────────────────────┐ │
│  Evaluación       │  │ PROVEEDORES          │ MODELOS                        │ CONFIGURACIÓN          │ │
│  Observabilidad   │  │                      │                                │                        │ │
│                   │  │ Buscar...            │ ANTHROPIC                    │ CLAUDE SONNET          │ │
│                   │  │                      │                                │                        │ │
│ > Proveedores     │  │ ● Anthropic        │ Buscar modelos...             │ ● Activo               │ │
│   y Modelos       │  │   tipo integrado          │                                │                        │ │
│                   │  │                      │ MODELO             ESTADO      │ Configuración | Uso    │ │
│  Configuración    │  │ ● Ollama Cloud       │                                │                        │ │
│                   │  │   tipo integrado          │ ☑ Claude Sonnet     ● Activo   │ Nombre                 │ │
│                   │  │                      │                                │ [Claude Sonnet      ] │ │
│                   │  │ ● OpenAI Codex (CLI) │ ☑ Claude Haiku      ● Activo   │                        │ │
│                   │  │   tipo integrado          │                                │ ID del modelo          │ │
│                   │  │                      │ ☐ Claude Opus       ○ Inactivo │ [anthropic...        ] │ │
│                   │  │ ● GitHub Copilot     │                                │                        │ │
│                   │  │   tipo integrado          │                                │ Capacidades            │ │
│                   │  │                      │                                │ Chat · Tools · Vision  │ │
│                   │  │ ● Ollama local       │                                │                        │ │
│                   │  │   tipo integrado          │                                │ Temperatura            │ │
│                   │  │                      │                                │ [0.7                 ] │ │
│                   │  │ ● OpenRouter         │                                │                        │ │
│                   │  │   tipo integrado          │                                │ Máximo tokens          │ │
│                   │  │                      │                                │ [4096                ] │ │
│                   │  │ ○ OpenCode           │                                │                        │ │
│                   │  │   Sin conexión       │                                │ Predeterminado para    │ │
│                   │  │                      │                                │ [Chat general       ▼] │ │
│                   │  │ [+ Añadir]           │ [Actualizar catálogo]          │                        │ │
│                   │  │                      │                                │ [Probar] [Guardar]     │ │
│                   │  └──────────────────────┴────────────────────────────────┴────────────────────────┘ │
│                   │                                                                                      │
│                   │  ┌──────────────────────────────────────────┬─────────────────────────────────────┐ │
│                   │  │ ENRUTAMIENTO Y MODELOS PREDETERMINADOS   │ PRUEBA RÁPIDA                       │ │
│                   │  │                                          │                                     │ │
│                   │  │ Chat general        [Claude Sonnet ▼]    │ Modelo: [Claude Sonnet          ▼] │ │
│                   │  │ Razonamiento        [Modelo       ▼]    │                                     │ │
│                   │  │ RAG                 [Modelo       ▼]    │ Mensaje de prueba                  │ │
│                   │  │ Embeddings          [Modelo       ▼]    │ [Escribe aquí...                 ] │ │
│                   │  │ Código              [Modelo       ▼]    │                                     │ │
│                   │  │ Visión              [Modelo       ▼]    │ [Ejecutar prueba]                   │ │
│                   │  └──────────────────────────────────────────┴─────────────────────────────────────┘ │
│                   │                                                                                      │
│                   │  ESTADO: Desarrollo                         Última actualización: --                 │
└───────────────────┴──────────────────────────────────────────────────────────────────────────────────────┘
```

Los modelos, cantidades y estados de esta representación son ilustrativos. Los siete tipos de proveedor del panel izquierdo corresponden al inventario integrado de BAGO; no indican que estén configurados o conectados.

La pantalla se divide en **cinco zonas funcionales**.

---

## Proveedores integrados que deben aparecer en el catálogo

La pantalla debe partir del inventario existente de BAGO. Esta lista representa **tipos de proveedor con integración en BAGO**; no afirma que estén configurados, autenticados o disponibles en cada instalación.

| Proveedor | Modalidad integrada | Evidencia en BAGO | Estado que debe mostrar la UI |
| --- | --- | --- | --- |
| Ollama local | Servicio local / CLI | Catálogo de BAGO y ruta local de chat | Configuración local; disponibilidad por comprobar |
| Ollama Cloud | API | Adaptador incluido en los contratos offline de proveedores | Sin conexión hasta verificar credenciales y servicio |
| OpenAI Codex | CLI delegada | Adaptador incluido en los contratos offline de proveedores | Requiere CLI autenticada; no equivale a OpenAI Platform |
| OpenAI Platform | API key | Descriptor separado en el catálogo BAGO | Sin conexión hasta verificar credenciales y servicio |
| GitHub Copilot | Adaptador `copilot` | Adaptador incluido en los contratos offline de proveedores | Mostrar la modalidad de autenticación admitida por la instalación |
| Anthropic | API | Adaptador incluido en los contratos offline de proveedores | Sin conexión hasta verificar credenciales y servicio |
| OpenRouter | API | Adaptador incluido en los contratos offline de proveedores | Sin conexión hasta verificar credenciales y servicio |
| OpenCode | API | Adaptador incluido en los contratos offline de proveedores | Sin conexión hasta verificar credenciales y servicio |

Los seis proveedores cloud (Ollama Cloud, OpenAI Codex, GitHub Copilot, Anthropic, OpenRouter y OpenCode) aparecen en la comprobación de contratos offline de BAGO. Esa comprobación usa transporte simulado: confirma el contrato del adaptador, no una llamada real, credenciales válidas ni disponibilidad del proveedor. La UI debe conservar separadas las etiquetas **integrado**, **configurado**, **conectado** y **modelo probado**.

El catálogo de BAGO contiene además descriptores/presets para otros servicios. No deben presentarse como integraciones verificadas por esta lista hasta que exista evidencia equivalente del adaptador y su ruta de ejecución. En particular, **OpenAI Platform** debe seguir separado de **OpenAI Codex (CLI)**.

> **Alcance de esta propuesta:** inventario leído del checkout de BAGO en `5fb6f2f0`. En el repositorio actual `BAGO_AGENTIC_DATA_LAB`, `ProviderSettings` y su API gestionan Ollama; el adaptador AWS Bedrock pertenece a la ruta gobernada de RAG/agente. Incluir estos siete tipos en el diseño no los hace automáticamente configurables ni ejecutables desde esta UI de ADL.

Fuentes consultadas en BAGO: `frontend/src/shared/provider-catalog.ts`, `backend/bago_core/commands/cmd_chat.py` y `backend/tests/test_cloud_provider_contracts.py`.

---

## 2. Panel izquierdo — Proveedores registrados

Esta zona muestra únicamente los proveedores configurados en BAGO.

Cada proveedor presenta:

* Nombre y logotipo.
* Estado de conexión.
* Número de modelos registrados.
* Número de modelos habilitados.
* Menú de acciones.

Al seleccionar un proveedor, el panel central muestra sus modelos.

### Añadir proveedor

Al pulsar «Añadir proveedor» aparece una ventana independiente.

```text
┌──────────────────────────────────────────────────┐
│ AÑADIR PROVEEDOR                             ×   │
├──────────────────────────────────────────────────┤
│                                                  │
│ Tipo de proveedor                                │
│ [ Ollama Cloud                               ▼ ] │
│                                                  │
│ Nombre de la conexión                            │
│ [ Ollama Cloud principal                     ] │
│                                                  │
│ Método de autenticación                          │
│ [ API Key                                     ▼ ] │
│                                                  │
│ Credencial                                       │
│ [ •••••••••••••••••••••••••••                  ] │
│                                                  │
│ Endpoint                                         │
│ [ https://api...                              ] │
│                                                  │
│ Timeout                                          │
│ [ 60 segundos                                ▼ ] │
│                                                  │
│ Estado                                           │
│ ○ Pendiente de verificar                         │
│                                                  │
│ [Cancelar]                  [Probar conexión]     │
│                                                  │
│                              [Guardar proveedor] │
└──────────────────────────────────────────────────┘
```

Se deben contemplar varios tipos de proveedor:

**Locales:** Ollama, LM Studio y endpoints compatibles.

**Externos:** OpenAI, Anthropic, Google, AWS Bedrock, etc.

**Personalizados:** cualquier endpoint compatible con una interfaz soportada, por ejemplo OpenAI-compatible.

No todos necesitan API Key. Ollama local, por ejemplo, puede funcionar sin ella; AWS Bedrock admite métodos de autenticación distintos.

Las credenciales no deben almacenarse como texto plano ni aparecer en los registros de ejecución.

---

## 3. Panel central — Catálogo de modelos

Una vez seleccionado el proveedor, aparecen sus modelos.

La lista permite:

**Activar/desactivar modelos:** determina cuáles puede utilizar BAGO.

**Asignar predeterminado:** establece qué modelo se utilizará para una función concreta.

**Consultar capacidades:** texto, razonamiento, herramientas, visión, embeddings, etc.

**Consultar disponibilidad:** distingue entre un modelo registrado y uno realmente accesible.

**Actualizar catálogo:** consulta los modelos del proveedor, si su API lo permite.

**Registrar modelo manualmente:** necesario cuando el proveedor no ofrece una API de descubrimiento.

### Estados de modelo

Hay una distinción esencial:

| Estado         | Significado                                              |
| -------------- | -------------------------------------------------------- |
| Registrado     | BAGO conoce su identificador y configuración.            |
| Habilitado     | Está autorizado para ser seleccionado.                   |
| Disponible     | Una comprobación reciente confirma que puede utilizarse. |
| No verificado  | Todavía no se ha comprobado su funcionamiento.           |
| Error          | Ha fallado la última comprobación.                       |
| Predeterminado | Está asignado a una función concreta.                    |

**Habilitado no significa disponible.**

Y tampoco significa que el modelo pueda ejecutar cualquier herramienta. La autorización de herramientas pertenece a otra frontera de BAGO.

---

## 4. Panel derecho — Configuración del modelo

Esta zona cambia en función del modelo seleccionado.

Organizaría sus controles en cuatro pestañas para evitar saturación visual.

```text
┌──────────────────────────────────────────────┐
│ MODELO SELECCIONADO                           │
│                                              │
│ Claude Sonnet                    ● Activo    │
│                                              │
│ Configuración | Parámetros | Uso | Pruebas   │
├──────────────────────────────────────────────┤
│                                              │
│ INFORMACIÓN                                  │
│                                              │
│ Nombre:      Claude Sonnet                   │
│ Proveedor:   AWS Bedrock                     │
│ Model ID:    anthropic...                    │
│                                              │
│ Capacidades:                                 │
│ [Chat] [Tools] [Vision]                      │
│                                              │
│ CONFIGURACIÓN                                │
│                                              │
│ Habilitado                         [ON]      │
│                                              │
│ Predeterminado para:                         │
│ [Chat general                           ▼]  │
│                                              │
│ PARÁMETROS                                   │
│                                              │
│ Temperatura        [0.7]                     │
│ Top P              [0.9]                     │
│ Máximo tokens      [4096]                    │
│                                              │
│ [Restaurar]                 [Guardar]         │
└──────────────────────────────────────────────┘
```

Los parámetros deben generarse según las capacidades reales del modelo.

Por ejemplo, un modelo de embeddings no necesita controles de temperatura de chat.

También es importante separar la configuración global del modelo de las preferencias de cada agente.

Un agente puede utilizar una temperatura distinta sin modificar la configuración general de BAGO.

---

## 5. Parte inferior — Enrutamiento y pruebas

Esta es una de las funciones más importantes.

BAGO no debería tener simplemente un único «modelo principal».

Debería permitir asignar modelos según su función.

```text
┌────────────────────────────────────────────────────────┐
│ ENRUTAMIENTO DE MODELOS                                │
├────────────────────────────────────────────────────────┤
│                                                        │
│ FUNCIÓN                  MODELO                         │
│                                                        │
│ Chat general             [Modelo A                 ▼]  │
│ Razonamiento             [Modelo B                 ▼]  │
│ Programación             [Modelo C                 ▼]  │
│ RAG / Síntesis           [Modelo D                 ▼]  │
│ Embeddings               [Modelo E                 ▼]  │
│ Visión                   [Modelo F                 ▼]  │
│                                                        │
│ [Guardar configuración]                                │
└────────────────────────────────────────────────────────┘
```

El selector debe mostrar únicamente modelos habilitados y compatibles con la función.

### Pruebas de conexión y modelo

Necesitamos dos acciones diferentes.

**Probar conexión:** comprueba autenticación y accesibilidad del proveedor.

**Probar modelo:** envía una petición real para comprobar que el modelo responde correctamente.

```text
┌──────────────────────────────────────────────┐
│ PRUEBA DE MODELO                             │
├──────────────────────────────────────────────┤
│                                              │
│ Modelo: Claude Sonnet                        │
│                                              │
│ Prompt                                       │
│ ┌──────────────────────────────────────────┐ │
│ │ Responde únicamente con la palabra OK. │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ [Ejecutar prueba]                             │
│                                              │
│ RESULTADO                                    │
│                                              │
│ Estado:         PASS                         │
│ Tiempo:         1.2 s                        │
│ Tokens entrada: 12                           │
│ Tokens salida:  3                            │
│ Coste:          Estimado                     │
│                                              │
│ [Ver detalles] [Ver evidencia]                │
└──────────────────────────────────────────────┘
```

La prueba debe advertir antes de consumir servicios facturables y nunca dispararse automáticamente al seleccionar un modelo.

Su resultado puede conservar un receipt con proveedor, modelo, fecha, latencia, configuración utilizada y resultado, sin almacenar secretos.

---

## 6. Utilidades adicionales necesarias

No añadiría muchas funciones más a esta pantalla, pero hay cinco que sí considero necesarias.

**1. Alcance de configuración**

Distinguir entre la configuración global de BAGO y las asignaciones específicas por proyecto.

Por ejemplo, un proyecto puede utilizar Ollama y otro AWS Bedrock sin modificar la configuración global.

**2. Límites de uso**

Configurar límites opcionales de solicitudes, tokens, concurrencia y gasto estimado.

Debe poderse distinguir entre límites impuestos por BAGO y cuotas reales del proveedor.

**3. Fallback**

Permitir elegir un modelo alternativo cuando falle el principal, siempre que sea compatible y esté expresamente permitido.

No debe cambiar automáticamente de un proveedor local a uno externo enviando datos sin autorización.

**4. Diagnóstico**

Mostrar errores de autenticación, modelo inexistente, proveedor inaccesible, timeout o cuota agotada.

**5. Dependencias**

Antes de desactivar o eliminar un modelo, BAGO debe indicar dónde está siendo utilizado.

Por ejemplo:

```text
┌──────────────────────────────────────────────┐
│ DESACTIVAR MODELO                            │
├──────────────────────────────────────────────┤
│                                              │
│ Claude Sonnet está asignado a:               │
│                                              │
│ • Chat general                               │
│ • Agente Frontend Auditor                    │
│ • Proyecto Agentic Data Lab                  │
│                                              │
│ La desactivación dejará estas asignaciones   │
│ sin un modelo disponible.                    │
│                                              │
│ [Cancelar]          [Revisar dependencias]   │
└──────────────────────────────────────────────┘
```

Esta comprobación debe consultar dependencias reales, no estimarlas.

---

## 7. Qué separaría en otras pantallas

Para mantener una carga cognitiva baja, no pondría aquí toda la administración de IA.

La pantalla **Proveedores y Modelos** se encarga de registrar conexiones, descubrir y habilitar modelos, establecer configuraciones generales, seleccionar predeterminados y ejecutar comprobaciones.

La configuración específica de un agente corresponde a **Agentes**.

Las herramientas permitidas pertenecen a **Herramientas y Autorización**.

Las fuentes de conocimiento y los documentos se administran desde **Contexto del proyecto / Datos**.

Las trazas y las evaluaciones detalladas se consultan desde **Observabilidad y Evaluación**, con enlaces desde la ficha del modelo.

De esta manera cada pantalla conserva una responsabilidad clara.

---

### NOTA FINAL — Propuesta de diseño

Mantendría **tres columnas principales: Proveedores → Modelos → Configuración**, más una sección inferior de enrutamiento y prueba rápida.

Es el esquema más apropiado para el funcionamiento que buscamos en ADL/BAGO: registrar proveedores, activar modelos, asignarlos a funciones y demostrar que funcionan.

**La regla arquitectónica principal sería:**

`PROVEEDOR REGISTRADO ≠ CONEXIÓN VERIFICADA ≠ MODELO HABILITADO ≠ MODELO AUTORIZADO PARA EJECUTAR HERRAMIENTAS`

Cada estado debe gestionarse y verificarse por separado.

---

## Estado de implementación en ADL

La pantalla actual organiza los registros en pestañas por proveedor. Cada ficha
presenta su modalidad de alta: sesión local o clave para Ollama, Codex CLI,
OpenAI Platform, GitHub Copilot CLI/token, Anthropic, OpenRouter y OpenCode.
Codex CLI y OpenAI Platform son fichas separadas.

El registro de proveedores que aún no tienen una ruta de ejecución en ADL se
guarda como `configured_unverified`. Sus claves solo se escriben en el almacén
de credenciales del sistema operativo; la API devuelve únicamente si existe
una clave. Guardar un registro no inicia OAuth, no ejecuta una CLI, no prueba la
conexión y no habilita ese proveedor en chat ni en ejecuciones de agentes.

Ollama conserva sus llamadas existentes de estado, configuración, carga de
modelos y comprobación no generativa. La ruta de chat de ADL continúa limitada
a Ollama. Bedrock permanece en su ruta gobernada de RAG/agente.
