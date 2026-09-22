---
name: bago-goal
description: Goal-driven task orchestration with BAGO closure and evidence. Use when the user says "achieve this", "make this work", "implement until done", or wants a verified, closure-sensitive completion of a non-trivial task in a single Pi session.
metadata:
  targetHarness: pi
  minPiVersion: 0.84.2
  lastUpdated: 2026-08-20
---

# BAGO Goal

Use este skill para objetivos con acceptance criteria, iteraciones y verificacion.

1. Entrevista al usuario para clarificar el objetivo y criterios.
2. Crea .goals/<id>/goal.md y status.json.
3. Ejecuta el plan paso a paso.
4. Realiza un Inspector pass con contexto fresco.
5. Cierra con terminos BAGO: EXECUTED, VERIFIED, VALIDATED, BLOCKED.
