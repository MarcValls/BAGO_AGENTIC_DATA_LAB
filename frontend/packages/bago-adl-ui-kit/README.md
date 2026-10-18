# BAGO ADL UI Kit

Pack reutilizable de estilos y componentes React para mantener una imagen común entre pantallas y proyectos basados en React.

## Contenido

- `tokens.css`: paleta, tipografía, espacios, radios y sombra. Está normalizada a partir de los colores y medidas que ya usa `frontend/src/App.css` y `frontend/src/components/WindowsSurface.css`.
- `components.css`: estilos aislados para los componentes del pack, con foco visible y adaptación móvil.
- `components.tsx` / `index.ts`: `BagoButton`, `BagoPanel`, `BagoPageHeader`, `BagoMetric`, `BagoStatus`, `BagoEmptyState`, `BagoTabStrip` y `BagoDataGrid`.

## Instalación manual

Copia esta carpeta al proyecto React consumidor. Instala los estilos una vez en su entrada:

```tsx
import './ui-kit/tokens.css'
import './ui-kit/components.css'
```

Importa componentes según la pantalla:

```tsx
import { BagoButton, BagoMetric, BagoPageHeader, BagoPanel, BagoStatus } from './ui-kit'

export function Overview() {
  return <main className="bago-ui">
    <BagoPageHeader kicker="Operación" title="Resumen" description="Estado actual del flujo." actions={<BagoButton variant="primary">Crear ejecución</BagoButton>} />
    <BagoPanel><BagoMetric label="Ejecuciones" value="12" hint="En los últimos 7 días" /></BagoPanel>
    <BagoStatus tone="success">Disponible</BagoStatus>
  </main>
}
```

Envuelve cada área que use el pack con `.bago-ui`. Así se limitan las reglas de base del pack y no se alteran botones o tablas ajenos. Las props y el contenido siguen siendo responsabilidad de cada aplicación.

## Convención visual

Usa superficies `bg → surface → panel → raised`, texto principal y secundario, un único azul de acción, y tonos semánticos solo para estados. Utiliza la escala `space-1` a `space-8`, radios `sm/md/lg` y deja que el foco visible indique navegación por teclado. Para nuevas variantes, añade tokens semánticos; evita colores puntuales en cada pantalla.

## Límites

Es un kit de componentes de presentación, sin dependencias de datos, router ni estado global. Los componentes son accesibles como base y cada integración debe conservar nombres de campos, etiquetas y acciones adecuadas a su contexto.
