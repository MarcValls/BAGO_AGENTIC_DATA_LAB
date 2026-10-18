# Navegación del chat por intención semántica

## Objetivo

Permitir que App assistant interprete solicitudes de navegación en lenguaje natural sin exigir una frase o etiqueta exacta. El modelo puede inferir una vista registrada; el servidor valida el destino mediante una lista determinista.

## Criterios de cierre

- Las solicitudes de navegación llegan al razonamiento del modelo, no a un mapa de frases predefinidas en la UI.
- El modelo solo puede solicitar una vista registrada; una intención ambigua no produce navegación.
- La lectura de archivos autorizada por turno mantiene sus límites, y los agentes seleccionados no reciben control de la aplicación.
- El tutorial explica la interacción sin presentar comandos memorizables.
- Backend compila, frontend construye y la comprobación del README pasa.
- La prueba de inferencia con el proveedor real queda claramente marcada como ejecutada o NOT_RUN.

## Estado

VERIFIED. El chat de control resuelve cada petición como `navigate`, `answer` o `clarify`, aporta significado a las vistas registradas y valida el destino antes de navegar. La suite completa, el build, la consistencia del README y cinco casos con Ollama local pasan en el alcance documentado en `evidence/VERIFICATION.md`.

## Evidencia

Ver `evidence/VERIFICATION.md`.
