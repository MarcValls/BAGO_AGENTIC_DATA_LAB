---
name: bago-reparador
description: Localiza, audita, diagnostica y repara BAGO sin asumir una versión, ruta o layout concretos. Use para encontrar la fuente y el runtime efectivos, detectar copias divergentes, validar CLI, sesiones, REPL, providers, comandos, UI y launchers, investigar fallos de arranque u orquestación, y cerrar una reparación con evidencia.
---

# Reparador BAGO

## Principio

Trabajar por capacidades observadas, no por nombres de carpeta, fechas o versiones declaradas.

Separar siempre:

- fuente editable;
- motor ejecutable;
- runtime activo;
- estado mutable del usuario;
- superficies cliente como CLI, chat o manager.

No asumir que están en la misma ruta ni que una versión igual implica contenido igual.

## Flujo normal

1. Localizar copias:

```text
python scripts/bago_paths.py
```

2. Seleccionar fuente y runtime usando roles, Git, entrypoints y capacidades detectadas.
3. Ejecutar el smoke en cada objetivo:

```text
python scripts/bago_smoke_diagnose.py --root <ROOT>
```

4. Comparar archivos críticos:

```text
python scripts/compare_copies.py --source <SOURCE> --runtime <RUNTIME>
```

5. Si el problema afecta routing, chat o comandos:

```text
python scripts/check_orchestration.py --root <ROOT>
```

Los scripts adaptan las comprobaciones a las capacidades disponibles. Una comprobación no soportada debe quedar como `SKIP`, no como un fallo inventado.

## Auditoría

Descubrir primero los validadores y scripts del proyecto. Ejecutar, según existan:

- versión y ayuda del entrypoint;
- validate, doctor o equivalentes;
- tests del motor;
- typecheck, tests y build de clientes;
- estado Git y metadatos de distribución;
- comparación fuente/runtime.

Separar fallos funcionales de tests que dependan de archivos deliberadamente no empaquetados. Leer [references/flujo_orquestacion.md](references/flujo_orquestacion.md) para las capas del sistema.

## Reparación

1. Reproducir en la fuente más actual.
2. Preservar cambios existentes.
3. Formular el contrato roto.
4. Aplicar el cambio mínimo en la fuente autorizada.
5. Añadir o ajustar una prueba representativa.
6. Repetir smoke, tests afectados y comparación.
7. Sincronizar, instalar o editar un runtime protegido solo con autorización explícita.

Leer [references/errores_comunes.md](references/errores_comunes.md) cuando aparezcan síntomas conocidos.

## Seguridad

- Diagnosticar en modo lectura por defecto.
- No hacer commit, push, instalación, elevación ni sincronización automáticamente.
- No convertir alertas de fixtures o canarios en secretos reales sin revisar contexto.
- No usar el perfil completo, la raíz de una unidad o una ruta no identificada como proyecto.
- Mantener el estado mutable fuera del runtime protegido.

Para sintaxis PowerShell, detectar primero y aplicar solo tras revisar:

```text
python scripts/fix_ps1_syntax.py <TARGET>
python scripts/fix_ps1_syntax.py <TARGET> --apply
```

## Entrega

Informar de forma breve:

- fuente, runtime y estado realmente usados;
- capacidades y versión observadas;
- pruebas ejecutadas;
- divergencias y causa probable;
- reparación realizada;
- riesgos o trabajo pendiente.
