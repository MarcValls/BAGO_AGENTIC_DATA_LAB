---
name: bago-core-batteries
description: Bateria de 4 plantillas de paso (P0 triage, P1 plan, P2 execute, P3 verify) para ejecutar cualquier tarea BAGO en Pi con disciplina, evidencia y cierre canonico.
metadata:
  targetHarness: pi
  minPiVersion: 0.84.2
  lastUpdated: 2026-08-20
---

# BAGO Core Batteries

Usa /bago-p0-triage, /bago-p1-plan, /bago-p2-execute, /bago-p3-verify secuencialmente.

- P0: Triage y reconocimiento (solo lectura).
- P1: Planificacion con goal.md inmutable.
- P2: Ejecucion con cambios minimos.
- P3: Verificacion con contexto fresco.
