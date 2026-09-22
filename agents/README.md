# Catálogo de agentes BAGO del laboratorio

Este directorio es un catálogo organizado por responsabilidad. Es una
colección de referencia dentro de `BAGO_AGENTIC_DATA_LAB`; no es un punto de
carga automático y no sustituye a `.github/agents`, `.codex/agents` ni a los
contratos canónicos de otro proyecto.

## Regla de procedencia

Los archivos se han copiado desde sus ubicaciones originales para conservar
las fuentes intactas. Las copias históricas y especializadas están incluidas
para comparación y recuperación, no para declararlas activas en el motor.

Consulta `CATALOG_MANIFEST.json` para ver las responsabilidades, la política
de procedencia y el estado del catálogo.

## Estructura

- `01-gobierno-orquestacion`: arranque, contexto, coordinación y entrega.
- `02-exploracion-arquitectura`: exploración, arquitectura, modularidad y rescate histórico.
- `03-backend-contratos`: backend, contratos y compatibilidad entre capas.
- `04-frontend-ui`: frontend, UI, estado y verificación visual.
- `05-seguridad-verdad`: seguridad, sinceridad operacional, comandos peligrosos y aislamiento.
- `06-tests-calidad-release`: tests, higiene, análisis, verificación y release.
- `07-sincronizacion`: sincronización Git, documentación y sincronizadores históricos.
- `08-runtime-supervision`: infraestructura interna de agentes.
- `09-activadores-no-agentes`: skills y paquetes de activación; no son agentes individuales.

El agente `bago-sync-agent` que ya existe en el proyecto sigue siendo la
definición operativa del laboratorio. La copia en este catálogo solo facilita
la agrupación por responsabilidad.
