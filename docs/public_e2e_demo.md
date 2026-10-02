# Demo de cliente ficticio: Bruma Market

Bruma Market es un minorista online inventado para ilustrar un problema
operativo reconocible: decidir qué hacer cuando un pedido exprés llega con más
de 24 horas de retraso. La política vigente devuelve el coste del envío y un
recibo de QA valida el cambio respecto a la versión anterior.

Todo el caso y sus datos son fixtures deterministas. No representan a un
cliente real ni se conectan a servicios externos.

## Instalar y ejecutar

Requisitos: Python 3.11+ y Bash. Desde la raíz del checkout:

```bash
bash scripts/install_demo.sh
.venv/bin/python scripts/bago.py demo
```

El instalador crea `.venv` e instala las dependencias fijadas en
`requirements.txt`. No modifica el entorno global. Para activar el entorno y
usar el comando corto:

```bash
source .venv/bin/activate
bago demo
```

Opciones útiles:

```bash
bago demo --json
bago demo --write-evidence
```

`--json` muestra el resumen máquina-legible. `--write-evidence` refresca
`evidence/public_e2e_demo.md` después de completar correctamente la ejecución.
Para ejecutar la demo sin el CLI, se mantiene disponible
`python scripts/run_public_e2e_demo.py --check`.

## Qué muestra

```text
Pregunta de negocio
  → Governed RAG con dos fuentes verificadas
  → Ontology Engine: política v2 sustituye v1 y QA la valida
  → respuesta con contexto fixture local
  → sandbox restringido ejecuta un test tipado
  → traza local y evaluación determinista
```

La salida de consola resume la respuesta, las fuentes recuperadas, el resultado
de las validaciones y el coste local de cero dólares.

## Límites

- Sin credenciales, cuenta cloud, Docker, red ni servicios de pago.
- El cliente LLM tiene forma compatible con Bedrock, pero es un fixture local;
  no se realiza ninguna llamada a AWS.
- La ejecución no valida integraciones live con AWS, OpenMetadata o
  commercetools, ni comportamiento de producción.
- La evidencia muestra únicamente lo que valida esta ruta local.

La CI ejecuta la misma demo y la suite de pruebas en
`.github/workflows/ci.yml`.
