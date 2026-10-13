"""Render the Bruma Market fictional-client walkthrough from local evidence."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence"
VIDEO = OUT / "bruma_market_demo_v1.mp4"
SUBTITLES = OUT / "bruma_market_demo_v1.es.srt"
NOTE = OUT / "bruma_market_demo_v1.md"
HASH = OUT / "bruma_market_demo_v1.mp4.sha256"
SOURCE = ROOT / "evidence" / "public_e2e_demo.md"
WIDTH, HEIGHT = 1920, 1080
BG = (15, 22, 34)
PANEL = (26, 37, 54)
PANEL_LIGHT = (35, 48, 67)
INK = (245, 242, 233)
MUTED = (174, 185, 198)
ORANGE = (255, 157, 92)
TEAL = (100, 220, 196)
BLUE = (124, 177, 255)
LAVENDER = (187, 169, 255)
SECONDS_PER_SCENE = 8.5


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf")
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


TITLE, SUBTITLE = font(62, True), font(29)
SECTION, BODY, SMALL = font(25, True), font(33), font(23)
NUMBER, METRIC = font(45, True), font(32, True)


SCENES = [
    {
        "tag": "CASO DE CLIENTE · SIMULACIÓN",
        "title": "Bruma Market",
        "subtitle": "Una pregunta de atención al cliente, con política y evidencia enlazadas.",
        "cards": [("CLIENTE", "Tienda online ficticia", ORANGE), ("CASO", "Envío exprés con más de 24 h de retraso", BLUE), ("DATOS", "Fixtures locales; sin datos personales", TEAL)],
        "caption": "Bruma Market es un cliente ficticio. La demostración usa fixtures locales y no contiene datos personales.",
    },
    {
        "tag": "01 · LA PREGUNTA",
        "title": "¿Qué corresponde al cliente?",
        "subtitle": "El equipo necesita responder con una regla vigente y su respaldo.",
        "quote": "¿Qué política aplica si un pedido exprés llega con más de 24 horas de retraso y qué evidencia valida la regla?",
        "cards": [("OBJETIVO", "Una respuesta concreta", ORANGE), ("CONDICIÓN", "Retraso superior a 24 horas", BLUE)],
        "caption": "La consulta pide una decisión concreta: qué regla aplica a un envío exprés retrasado y qué evidencia la valida.",
    },
    {
        "tag": "02 · RECUPERACIÓN GOBERNADA",
        "title": "La respuesta sigue las fuentes",
        "subtitle": "El agente encuentra la política y el recibo de QA que la valida.",
        "cards": [("POLÍTICA VIGENTE", "Devuelve el coste del envío exprés", ORANGE), ("VALIDACIÓN", "Recibo de QA asociado a la regla", TEAL), ("RECUPERACIÓN", "2 fragmentos enlazados", BLUE)],
        "caption": "La recuperación local encuentra dos fragmentos: la política vigente y el recibo de QA asociado.",
    },
    {
        "tag": "03 · RESPUESTA",
        "title": "Respuesta útil y verificable",
        "subtitle": "Una conclusión de negocio con referencias que se pueden inspeccionar.",
        "quote": "Para pedidos exprés con más de 24 horas de retraso, se devuelve el coste del envío. El acta de QA valida la regla.",
        "cards": [("REGLA", "Reembolso del envío exprés", ORANGE), ("RESPALDO", "Política v2 + validación QA", TEAL)],
        "caption": "La respuesta indica el reembolso del coste del envío y enlaza la política vigente con la validación de QA.",
    },
    {
        "tag": "04 · EVIDENCIA",
        "title": "Cada afirmación conserva su origen",
        "subtitle": "Las referencias identifican revisión y tipo de evidencia.",
        "cards": [("REGLA", "bruma-delivery-policy-v2 · revisión 2.0.0", ORANGE), ("VALIDACIÓN", "bruma-delivery-policy-qa · revisión 1.0.0", TEAL), ("TRAZA", "15 eventos enlazan el recorrido", BLUE)],
        "caption": "Las referencias apuntan a la política v2 y al recibo de QA. Una traza local enlaza las etapas del recorrido.",
    },
    {
        "tag": "05 · CONTROL Y EJECUCIÓN",
        "title": "La ejecución tiene límites claros",
        "subtitle": "La demo recorre autorización, sandbox local y recibos.",
        "flow": ["Pregunta", "Recuperación", "Permiso", "Sandbox local", "Recibo"],
        "cards": [("SANDBOX", "LocalRestrictedBackend · perfil test_runner", BLUE), ("RED", "Sin acceso de red", TEAL), ("AWS LIVE", "NOT_RUN", ORANGE)],
        "caption": "La ejecución observada usa un sandbox local de pruebas y deniega la red. No se realiza ninguna llamada a AWS.",
    },
    {
        "tag": "06 · EVALUACIÓN LOCAL",
        "title": "El recorrido queda evaluado",
        "subtitle": "La evaluación comprueba estructura, permisos y enlaces de evidencia.",
        "metrics": [("PASS", "resultado", TEAL), ("1.00", "checks estructurales", BLUE), ("0", "contradicciones", ORANGE)],
        "cards": [("15", "eventos de traza", LAVENDER), ("2", "fragmentos recuperados", BLUE), ("0.0 USD", "ejecución local documentada", TEAL)],
        "caption": "La evaluación local registra PASS: comprueba estructura y enlaces de gobernanza; no mide la calidad general de un modelo.",
    },
    {
        "tag": "BRUMA MARKET · CIERRE",
        "title": "Una respuesta con límites visibles",
        "subtitle": "Regla, evidencia, autorización y recibo dentro del mismo recorrido.",
        "cards": [("RESULTADO", "Política aplicable + respaldo QA", ORANGE), ("ALCANCE", "Cliente ficticio · fixtures deterministas", TEAL), ("FRONTERAS", "AWS y servicios remotos: NOT_RUN", BLUE)],
        "caption": "Caso ficticio basado en la evidencia local del proyecto. Los servicios remotos permanecen sin ejecutar.",
    },
]


def wrap(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_width: int, use_font: ImageFont.FreeTypeFont, color=INK, spacing=10) -> int:
    lines: list[str] = []
    for paragraph in text.splitlines():
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=use_font) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=use_font, fill=color)
        y += use_font.size + spacing
    return y


def render_scene(index: int, scene: dict, path: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.ellipse((1390, -390, 2220, 450), fill=(23, 36, 54))
    draw.ellipse((-520, 760, 300, 1580), fill=(22, 35, 48))
    draw.rounded_rectangle((88, 70, 520, 124), radius=24, fill=PANEL_LIGHT)
    draw.text((112, 83), scene["tag"], font=SMALL, fill=ORANGE)
    draw.text((92, 165), scene["title"], font=TITLE, fill=INK)
    wrap(draw, scene["subtitle"], 98, 250, 1640, SUBTITLE, MUTED, 8)
    draw.line((98, 330, 1822, 330), fill=(54, 69, 88), width=2)

    if "quote" in scene:
        draw.rounded_rectangle((100, 385, 1810, 635), radius=24, fill=PANEL, outline=(62, 80, 101), width=2)
        draw.rounded_rectangle((100, 385, 112, 635), radius=6, fill=ORANGE)
        wrap(draw, scene["quote"], 148, 435, 1580, font(42, True), INK, 16)
    elif "flow" in scene:
        boxes = scene["flow"]
        start_x, gap, box_w = 112, 28, 300
        for n, label in enumerate(boxes):
            x = start_x + n * (box_w + gap)
            color = [ORANGE, BLUE, LAVENDER, TEAL, ORANGE][n]
            draw.rounded_rectangle((x, 425, x + box_w, 555), radius=20, fill=PANEL, outline=color, width=2)
            wrap(draw, label, x + 20, 461, box_w - 38, SECTION, INK, 6)
            if n < len(boxes) - 1:
                draw.line((x + box_w + 6, 490, x + box_w + gap - 7, 490), fill=MUTED, width=3)
                draw.polygon([(x + box_w + gap - 8, 482), (x + box_w + gap, 490), (x + box_w + gap - 8, 498)], fill=MUTED)
    elif "metrics" in scene:
        for n, (value, label, accent) in enumerate(scene["metrics"]):
            x = 108 + n * 580
            draw.rounded_rectangle((x, 400, x + 530, 585), radius=25, fill=PANEL, outline=(59, 77, 99), width=2)
            draw.text((x + 30, 430), value, font=NUMBER, fill=accent)
            wrap(draw, label, x + 30, 495, 460, SECTION, MUTED, 5)

    cards = scene.get("cards", [])
    if cards:
        top = 690 if "quote" in scene else (625 if "flow" in scene or "metrics" in scene else 400)
        count = len(cards)
        gap = 24
        card_w = (1710 - gap * (count - 1)) // count
        for n, (label, value, accent) in enumerate(cards):
            x = 105 + n * (card_w + gap)
            draw.rounded_rectangle((x, top, x + card_w, top + 205), radius=20, fill=PANEL, outline=(54, 71, 92), width=2)
            draw.rounded_rectangle((x, top, x + 9, top + 205), radius=4, fill=accent)
            draw.text((x + 26, top + 24), label, font=SMALL, fill=accent)
            wrap(draw, value, x + 26, top + 72, card_w - 52, BODY, INK, 8)

    # An understated progress rail keeps the video legible as a short sequence.
    draw.rounded_rectangle((98, 948, 1822, 957), radius=5, fill=(43, 57, 75))
    draw.rounded_rectangle((98, 948, int(98 + 1724 * (index + 1) / len(SCENES)), 957), radius=5, fill=ORANGE)
    draw.text((100, 977), "BAGO AGENTIC DATA LAB  /  DEMO LOCAL", font=SMALL, fill=MUTED)
    draw.text((1708, 977), f"{index + 1:02d}  /  {len(SCENES):02d}", font=SMALL, fill=MUTED)
    image.save(path, format="PNG", optimize=True)


def srt_stamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{millis:03}"


def render() -> dict:
    source_text = SOURCE.read_text(encoding="utf-8")
    required_evidence = [
        "Bruma Market (cliente ficticio)",
        "fixture.public-e2e",
        "AWS live: `NOT_RUN`",
        "Evaluation: `PASS` (`1.00`)",
    ]
    missing = [item for item in required_evidence if item not in source_text]
    if missing:
        raise RuntimeError(f"Source evidence is missing expected Bruma demo claims: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bruma-market-video-") as temp:
        frame_dir = Path(temp)
        for index, scene in enumerate(SCENES, start=1):
            render_scene(index - 1, scene, frame_dir / f"frame-{index:02d}.png")
        command = [
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", "2/17",
            "-i", str(frame_dir / "frame-%02d.png"), "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-t",
            str(len(SCENES) * SECONDS_PER_SCENE), "-movflags", "+faststart", str(VIDEO),
        ]
        subprocess.run(command, check=True)

    blocks = []
    for index, scene in enumerate(SCENES):
        start = index * SECONDS_PER_SCENE
        end = (index + 1) * SECONDS_PER_SCENE
        blocks.append(f"{index + 1}\n{srt_stamp(start)} --> {srt_stamp(end)}\n{scene['caption']}\n")
    SUBTITLES.write_text("\n".join(blocks), encoding="utf-8")
    digest = hashlib.sha256(VIDEO.read_bytes()).hexdigest()
    HASH.write_text(f"{digest}  {VIDEO.name}\n", encoding="ascii")
    source_digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    NOTE.write_text(
        "# Bruma Market — demo de cliente ficticio\n\n"
        "Vídeo explicativo de un caso de atención de pedidos exprés con más de 24 horas de retraso. "
        "Las pantallas son una composición visual basada en la evidencia local citada abajo; "
        "no son una grabación de una sesión en vivo.\n\n"
        "## Artefactos\n\n"
        f"- Vídeo MP4: `{VIDEO.name}` ({len(SCENES) * SECONDS_PER_SCENE:.1f} s, 1920×1080, sin narración de audio).\n"
        f"- Subtítulos en español: `{SUBTITLES.name}`.\n"
        f"- SHA-256 MP4: `{digest}`.\n"
        f"- SHA-256 fuente de evidencia: `{source_digest}` (`{SOURCE.relative_to(ROOT).as_posix()}`).\n"
        f"- Renderizador reproducible: `scripts/{Path(__file__).name}`.\n\n"
        "## Alcance demostrado\n\n"
        "Bruma Market es ficticio. La demo describe recuperación de dos fragmentos de fixture, "
        "la regla de devolución del coste del envío exprés, su validación QA, y un recorrido local "
        "con sandbox, recibos y evaluación estructural PASS.\n\n"
        "Es una composición basada en `evidence/public_e2e_demo.md`, no una llamada a un "
        "proveedor remoto ni una transacción real. AWS live y OpenMetadata live permanecen `NOT_RUN`; "
        "la evaluación PASS comprueba estructura y enlaces de evidencia, no la calidad general "
        "de un modelo ni preparación para producción. Los datos son fixtures locales y la demo "
        "no contiene datos de clientes reales.\n",
        encoding="utf-8",
    )
    return {"video": VIDEO.relative_to(ROOT).as_posix(), "subtitles": SUBTITLES.relative_to(ROOT).as_posix(), "duration_seconds": len(SCENES) * SECONDS_PER_SCENE, "sha256": digest, "bytes": VIDEO.stat().st_size, "source_sha256": source_digest}


if __name__ == "__main__":
    print(render())
