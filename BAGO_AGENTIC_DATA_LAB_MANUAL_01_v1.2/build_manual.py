#!/usr/bin/env python3
"""Build Manual 01 PDF, HTML preview, contact sheet and package integrity files."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "MANUAL_PARA_DUMMIES_assets"
PDF = ROOT / "BAGO_ADL_MANUAL_COMO_LEER_UNA_EJECUCION_v1.3.pdf"

PAGES = [
    ("INICIO", "Leer una ejecución", "Manual 01 · edición 1.3 · 15 octubre 2026", """
    <p class="lead">Guía para inspeccionar una ejecución del laboratorio, seguir su LocalTrace y revisar propuestas y recibos.</p>
    <h2>Abrir la aplicación</h2>
    <pre>scripts\\run-local-ui.ps1</pre>
    <p>Ejecuta el comando desde la raíz del repositorio. El launcher compila la interfaz, inicia la API local y abre la aplicación. Selecciona un puerto libre entre 8080 y 9000; usa la dirección que abre el propio launcher. Para dependencias, consulta <code>docs/agent-chat-control/LOCAL_SETUP.md</code>.</p>
    <p>En la barra lateral, elige <b>Inspect</b> y después <b>Decision Inspector</b>. La interfaz es de solo lectura: no autoriza ni ejecuta acciones. Si no hay paquete de evidencias, indica que falta; no inventa una ejecución.</p>
    <div class="note"><b>Alcance de la app.</b> También incluye Chat, Capabilities, Agent Builder, Agent Runs y Agent Evaluation Lab. Conversar con un agente o ver una entrada no demuestra por sí solo que un trabajo se completara. Consulta <code>portfolio/README.md</code> para la demo gobernada.</div>
    <img src="MANUAL_PARA_DUMMIES_assets/overview.png" alt="Captura anterior del Decision Inspector">
    <p class="caption">Captura de referencia validada el 8 de octubre de 2026; puede diferir de la interfaz actual.</p>
    """),
    ("01 · OBSERVAR", "Decisión, claims y evidencia", "Identifica el run antes de interpretar la respuesta.", """
    <p class="lead">Anota el <code>run_id</code>, la pregunta, la respuesta fuente y el estado de la ejecución.</p>
    <p>Los contadores resumen referencias de evidencia, claims estructurados, eventos de traza y acciones propuestas. Una referencia recuperada dice que un documento o fragmento se consultó; no demuestra por sí sola una frase de la respuesta.</p>
    <p>La interfaz no extrae claims del texto ni deduce relaciones claim-evidencia. En <b>Conclusion</b>, <b>Claims</b>, <b>Evidence</b> y <b>Provenance</b>, comprueba qué datos proporcionó la fuente. Si falta la revisión o snapshot, la frescura no queda establecida.</p>
    <div class="callout">No confundas “evidencia consultada” con “evidencia que respalda una afirmación”. El vínculo debe venir explícitamente de la fuente.</div>
    <h2>Preguntas para revisar</h2><ul><li>¿Qué ejecución estoy viendo?</li><li>¿La fuente separó claims estructurados?</li><li>¿Cada relación con evidencia aparece en los datos?</li><li>¿Se informó la revisión y la frescura?</li></ul>
    """),
    ("02 · SEGUIR", "Leer LocalTrace", "Orden y causalidad son datos distintos.", """
    <p class="lead">Abre <b>Trace</b> en el inspector. Revisa el <code>trace_id</code>, el <code>run_id</code>, la secuencia de eventos y las referencias registradas.</p>
    <p>La secuencia indica orden. Solo un <code>parent_event_id</code> informado por la fuente expresa una relación padre-hijo; no infieras más causalidad.</p>
    <table><tr><th>Identificador</th><th>Qué identifica</th></tr><tr><td><code>run_id</code></td><td>La ejecución del agente.</td></tr><tr><td>LocalTrace <code>trace_id</code></td><td>El registro local de eventos.</td></tr><tr><td>Jaeger Trace ID</td><td>La traza que consultó Jaeger local; puede ser distinto.</td></tr></table>
    <p>La interfaz no enlaza automáticamente el ID de Jaeger con el trace local. Si un dato falta, anótalo como no proporcionado.</p>
    <img src="MANUAL_PARA_DUMMIES_assets/trace.png" alt="Captura anterior de la cronología">
    <p class="caption">Captura de referencia del 8 de octubre; IDs y eventos cambian entre ejecuciones.</p>
    """),
    ("03 · COMPROBAR", "Acciones y recibos", "Permiso, ejecución y resultado necesitan evidencias distintas.", """
    <ol><li><b>Propuesta:</b> describe una intención.</li><li><b>Autorización:</b> indica si se permitió o denegó la solicitud.</li><li><b>Ejecución:</b> requiere que la fuente registre que el efecto ocurrió.</li><li><b>Recibo:</b> registra el resultado y debe asociarse a la misma ejecución.</li></ol>
    <p>Un permiso <code>ALLOW</code> no demuestra ejecución. Un <code>SUCCESS</code> sin recibo asociado no basta para verificar el resultado. El inspector asocia recibos solo si su <code>run_id</code> explícito coincide con el del agente. Un recibo sin identidad o de otro run queda sin verificar.</p>
    <div class="callout">La coincidencia del <code>run_id</code> es una comprobación de identidad declarada por la fuente; no es una firma criptográfica.</div>
    <img src="MANUAL_PARA_DUMMIES_assets/actions.png" alt="Captura anterior de acciones y recibos">
    <p class="caption">Captura de referencia del 8 de octubre; consulta los IDs y estados de la ejecución abierta.</p>
    """),
    ("04 · LOCALIZAR", "Jaeger local (opcional)", "Jaeger proyecta observabilidad; LocalTrace conserva la evidencia de eventos.", """
    <p>Se necesita Docker para reproducir la validación local documentada:</p>
    <pre>docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check</pre>
    <p>Abre <code>http://localhost:16686</code> y busca el Trace ID que imprima la ejecución actual. No reutilices el ID de una captura anterior. Al terminar, puedes detener Jaeger:</p>
    <pre>docker compose -p bago-otel -f infra/observability/docker-compose.yml down</pre>
    <img src="MANUAL_PARA_DUMMIES_assets/jaeger.png" alt="Captura anterior de Jaeger">
    <p class="caption">Captura histórica de Jaeger. El grafo y los identificadores variarán al repetir el flujo.</p>
    <div class="note">La validación versionada del 8 de octubre observó 15 spans para aquella traza. Es evidencia histórica, no prueba del estado actual de Docker, AWS ni colectores remotos. Este recorrido no acredita envío remoto.</div>
    """),
    ("05 · PRACTICAR", "Registra lo que observas", "Escribe conclusiones que se sostienen en los datos.", """
    <ul><li><code>run_id</code> y estado de la ejecución.</li><li>Número de referencias y presencia de claims estructurados.</li><li><code>trace_id</code>, eventos y relaciones padre informadas.</li><li>Propuestas, decisiones, efectos observados y recibos.</li><li>Si coinciden el <code>run_id</code> del recibo y el del agente.</li><li>Si consultaste Jaeger: Trace ID y spans observados.</li></ul>
    <div class="callout">Ejemplo de conclusión acotada: “El recibo declara el mismo run_id que esta ejecución y muestra resultado SUCCESS”. No afirmes que una referencia respalda una claim si el vínculo no está registrado.</div>
    <h2>Si algo no aparece</h2><ul><li><b>La app no abre:</b> usa la URL que lanzó el script; el puerto puede variar. Revisa <code>docs/agent-chat-control/LOCAL_SETUP.md</code>.</li><li><b>No hay evidencias:</b> la interfaz puede indicar que falta el paquete y ofrecer Agent Runs. La ausencia no demuestra que haya ocurrido una ejecución.</li><li><b>Faltan claims o soporte:</b> la fuente no los proporcionó; no los infieras de una cita.</li><li><b>Jaeger no abre:</b> verifica Docker y repite Compose. Si no se reproduce, deja el resultado como no verificado.</li></ul>
    <h2>Glosario</h2><p><b>Claim:</b> afirmación estructurada de la fuente. <b>Evidencia:</b> referencia a documento o fragmento consultado. <b>LocalTrace:</b> registro local de eventos. <b>Span:</b> operación en la traza de Jaeger. <b>Recibo:</b> registro del resultado declarado por una operación.</p>
    <p class="caption">Edición 1.3 actualizada con el código y la documentación del repositorio a 15 de octubre de 2026. La aplicación y Jaeger no estaban activos durante la actualización, por lo que las capturas siguen siendo referencias del 8 de octubre. Esta guía no certifica una nueva ejecución ni disponibilidad remota.</p>
    """),
]

CSS = """
@page { size: A4; margin: 17mm 18mm 18mm; @bottom-right { content: "BAGO ADL · Manual 01 · " counter(page); color:#587083; font-size:8pt; } }
* { box-sizing:border-box; } body { margin:0; color:#183143; font:10.5pt/1.52 "Segoe UI", Arial, sans-serif; }
.page { page-break-after:always; min-height:255mm; position:relative; } .page:last-child { page-break-after:auto; }
.brand { color:#187a9b; font-size:9pt; letter-spacing:2px; font-weight:700; text-transform:uppercase; border-bottom:2px solid #19a0ba; padding:0 0 8px; }
.kicker { margin-top:26mm; color:#1689a6; font-weight:700; letter-spacing:2px; text-transform:uppercase; }
h1 { font-size:33pt; line-height:1.07; margin:8mm 0; color:#10314a; } h2 { font-size:17pt; margin:8mm 0 3mm; color:#103d59; }
.subtitle { color:#567183; font-size:13pt; margin-bottom:13mm; } .lead { color:#35576b; font-size:13pt; line-height:1.45; }
p { margin:4mm 0; } ul,ol { padding-left:7mm; } li { padding:1.2mm 0; }
pre { background:#102b3e; color:#f1f7fa; padding:5mm; border-radius:3mm; white-space:pre-wrap; font:9.5pt/1.5 Consolas,monospace; }
code { font:9pt Consolas,monospace; color:#12647d; } table { width:100%; border-collapse:collapse; margin:5mm 0; } th,td { border:1px solid #c8d8e0; padding:3mm; text-align:left; } th { background:#e9f3f6; }
img { display:block; max-width:100%; max-height:95mm; object-fit:contain; margin:7mm auto 2mm; border:1px solid #c5d4dc; }
.caption { color:#607989; font-size:8.5pt; } .note,.callout { margin:6mm 0; padding:4mm 5mm; border-left:4px solid #1292ad; background:#eaf5f7; }
"""


def render_pdf(html_path: Path) -> None:
    try:
        from weasyprint import HTML  # type: ignore
        HTML(filename=str(html_path), base_url=str(ROOT)).write_pdf(str(PDF))
        return
    except ImportError:
        pass
    edge = shutil.which("msedge.exe") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not Path(edge).is_file():
        raise RuntimeError("Instala las dependencias de requirements.txt o proporciona Microsoft Edge para generar el PDF.")
    profile = ROOT / ".edge-pdf-profile"
    try:
        subprocess.run([edge, "--headless", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}", f"--print-to-pdf={PDF}", "--no-pdf-header-footer", html_path.as_uri()], check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    for name in ("overview.png", "trace.png", "actions.png", "jaeger.png"):
        if not (ASSETS / name).is_file():
            raise FileNotFoundError(f"Falta la captura de referencia: {ASSETS / name}")
    page_html = []
    for index, (kicker, title, subtitle, body) in enumerate(PAGES):
        page_html.append(f'<section class="page"><div class="brand">BAGO · Agentic Data Lab</div><p class="kicker">{html.escape(kicker)}</p><h1>{html.escape(title)}</h1><p class="subtitle">{html.escape(subtitle)}</p>{body}</section>')
    (ROOT / "estilos.css").write_text(CSS, encoding="utf-8")
    full_html = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>BAGO ADL · Manual 01 · edición 1.3</title><link rel="stylesheet" href="estilos.css"></head><body>{"".join(page_html)}</body></html>'
    html_path = ROOT / "manual.html"
    html_path.write_text(full_html, encoding="utf-8")
    render_pdf(html_path)

    import fitz
    document = fitz.open(PDF)
    thumbs = []
    for page in document:
        pix = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        thumbs.append(ImageOps.pad(image, (360, 510), color="white"))
    columns = 3
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 380, rows * 530), "#dce5e9")
    for index, thumb in enumerate(thumbs):
        x = (index % columns) * 380 + 10
        y = (index // columns) * 530 + 10
        sheet.paste(thumb, (x, y))
    sheet.save(ROOT / "PREVIEW_CONTACT_SHEET.png")

    excluded = {"MANIFEST.json", "SHA256SUMS.txt"}
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name not in excluded and not any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            data = path.read_bytes()
            entries.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    manifest = {"title": "BAGO Agentic Data Lab · Manual 01", "edition": "1.3", "updated": "2026-10-15", "pdf": PDF.name, "pages": len(document), "capturas": "referencia 2026-10-08; no refrescadas", "files": entries}
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = []
    for entry in entries:
        sums.append(f"{entry['sha256']}  {entry['path']}")
    for name in ("MANIFEST.json", "PREVIEW_CONTACT_SHEET.png", PDF.name):
        path = ROOT / name
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}")
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"PDF generado: {PDF}")
    print(f"Páginas: {len(document)}")
    print("HTML, vista previa, manifest y SHA256SUMS actualizados")


if __name__ == "__main__":
    main()
