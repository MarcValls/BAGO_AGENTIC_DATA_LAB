from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse


def create_manual_router(repo_root: Callable[[], Path]) -> APIRouter:
    router = APIRouter()

    @router.get("/manual", response_class=HTMLResponse)
    def user_manual() -> HTMLResponse:
        """Serve the curated manual; never read a caller-selected file or workspace."""
        return _render_curated_manual(repo_root() / "docs" / "public-web" / "MANUAL.md")

    @router.get("/manual/escritura-revisada", response_class=HTMLResponse)
    def reviewed_write_manual() -> HTMLResponse:
        """Fixed packaged guide; query parameters cannot select a source file."""
        return _render_curated_manual(repo_root() / "docs" / "agent-write" / "MANUAL_ES.md")

    return router


def _render_curated_manual(source: Path) -> HTMLResponse:
    if not source.is_file():
        raise HTTPException(status_code=503, detail="El manual no está incluido en esta instalación.")
    import markdown
    body = markdown.markdown(source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc"])
    document = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>BAGO ADL · Manual</title><style>'
                'body{margin:0;background:#0c1220;color:#f2efea;font:17px/1.65 system-ui,sans-serif}'
                'main{max-width:960px;margin:auto;padding:40px 24px}a{color:#8dc7e2}'
                'h1,h2,h3{line-height:1.25}h2{margin-top:2.2em;border-top:1px solid #33485a;padding-top:1em}'
                'pre{overflow:auto;padding:18px;background:#152334}code{font-size:.9em}'
                'table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #33485a;text-align:left}'
                '</style></head><body><main><nav aria-label="Manuales">'
                '<a href="/manual">Manual general</a> · '
                '<a href="/manual/escritura-revisada">Escritura revisada y Docker</a>'
                '</nav>' + body + '</main></body></html>')
    return HTMLResponse(document, headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache",
    })


