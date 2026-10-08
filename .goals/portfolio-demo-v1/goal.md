# Goal — Portfolio Demo v1 (FREEZE → TAG → 60–90s DEMO VIDEO → JAEGER/RECEIPTS → CV/LINKEDIN)

**Status:** ACCEPTED (inmutable; cambios solo via superseding goal)
**Branch:** `main`
**Tag name:** `portfolio-demo-v1` (annotated)
**Scope:** repo working tree at HEAD of `main` on 2026-10-02

## Objective

Producir, en una sola sesión Pi, el snapshot "portfolio demo v1" del
BAGO Agentic Data Lab con entregables inmediatamente utilizables para
CV y LinkedIn, **sin introducir nuevas afirmaciones cloud/AWS remotas**
más allá de las que `STATE.md` ya declara como VERIFIED, NOT_RUN o
NOT_PROVEN.

## Acceptance criteria

A1. Tag anotado `portfolio-demo-v1` creado en `main`, apuntando al
    HEAD actual, con mensaje que cite L0–L15 + LLM zero-cost rule.
B1. `git push origin portfolio-demo-v1` ejecutado y verificado con
    `git ls-remote`.
C1. Vídeo nuevo `evidence/portfolio_demo_v1.mp4` de 60–90s, contenedor
    MP4, códec reproducible por ffmpeg; representa el camino
    compuesto RAG gobernado + sandbox tipado + Jaeger L15, con
    frames basados en evidence real (no slides inventadas).
C2. Hash SHA-256 escrito en `evidence/portfolio_demo_v1.mp4.sha256`.
C3. Duración medida con `ffprobe` cae en [60s, 90s].
D1. Capturas Jaeger: si Docker está disponible y arranca, regenerar
    `evidence/l15_otel_jaeger_live.md` y persistir
    `evidence/l15_jaeger_query.png` + `evidence/l15_jaeger_trace.png`
    capturando la UI en `http://localhost:16686`.
D2. Si Docker no arranca, fallback a evidence ya inmutable
    (`l15_otel_jaeger_live.md` previo) y registrar el fallo como
    NOT_RUN con la causa exacta.
E1. `docs/cv_linkedin/portfolio-demo-v1.md` con: bullets CV,
    descripción LinkedIn Project (≤ 3000 chars), 5 highlights,
    tabla skills↔evidencia, links a tag/commit/evidence.
E2. `README.md` referenciando el tag y `docs/cv_linkedin/portfolio-demo-v1.md`.

## Hard constraints

- No añadir nuevas afirmaciones VERIFIED sobre AWS remoto,
  OpenMetadata remoto, commercetools live o KB live.
- No mutar STATE.md fuera de una posible nota al pie para el
  freeze; ningún cambio que contradiga su contenido.
- No introducir dependencias nuevas en `requirements.txt`.
- No commit si working tree estaba dirty en origen distinto al
  scope del freeze.
- Reproducibilidad: `python scripts/run_public_e2e_demo.py --check`
  debe seguir PASS.

## Closure

El goal se cierra cuando cada criterio A/B/C/D/E tiene evidencia
verificable. Si Docker no arranca y el fallback deja D2 como
NOT_RUN, el goal **se cierra igualmente** pero se documenta la
causa en `evidence/l15_jaeger_capture_attempt.md` con la salida
del intento.