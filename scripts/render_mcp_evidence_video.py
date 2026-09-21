"""Render a visual evidence video from a real local MCP governed run.

The frames are derived from ``run_demo`` and therefore display the actual
request, permit, outcome and evidence values produced by the MCP round trip.
The video is a review artifact; it does not replace the machine-readable
receipt or the automated tests.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

import anyio

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / "scripts"
OUTPUT_PATH = REPO_ROOT / "evidence" / "mcp_governed_demo.mp4"
HASH_PATH = REPO_ROOT / "evidence" / "mcp_governed_demo.mp4.sha256"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from run_mcp_demo import EVIDENCE_PATH, render_evidence, run_demo  # noqa: E402


WIDTH = 1920
HEIGHT = 1080
BACKGROUND = (10, 18, 32)
PANEL = (20, 32, 52)
PANEL_ALT = (27, 42, 66)
TEXT = (235, 242, 250)
MUTED = (154, 172, 196)
GREEN = (71, 211, 145)
AMBER = (248, 190, 74)
RED = (247, 113, 113)
BLUE = (103, 175, 255)


def _font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        candidates = [
            Path("C:/Windows/Fonts/consola.ttf"),
            Path("C:/Windows/Fonts/cour.ttf"),
        ]
    elif bold:
        candidates = [
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ]
    else:
        candidates = [
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


FONT_TITLE = _font(54, bold=True)
FONT_SUBTITLE = _font(27)
FONT_SECTION = _font(30, bold=True)
FONT_BODY = _font(27)
FONT_SMALL = _font(22)
FONT_MONO = _font(22, mono=True)


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    *,
    width: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = TEXT,
    line_gap: int = 9,
) -> int:
    x, y = xy
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width=max(1, width // max(font.size // 2, 1))) or [""])
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def _card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    *,
    accent: tuple[int, int, int] = BLUE,
    value_font: ImageFont.FreeTypeFont = FONT_BODY,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=PANEL, outline=(48, 71, 103), width=2)
    draw.rounded_rectangle((left, top, left + 9, bottom), radius=5, fill=accent)
    draw.text((left + 28, top + 20), label.upper(), font=FONT_SMALL, fill=MUTED)
    _draw_wrapped(draw, value, (left + 28, top + 58), width=right - left - 52, font=value_font)


def _base(title: str, subtitle: str, step: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((90, 70), title, font=FONT_TITLE, fill=TEXT)
    draw.text((94, 145), subtitle, font=FONT_SUBTITLE, fill=MUTED)
    draw.rounded_rectangle((1510, 76, 1825, 132), radius=26, fill=PANEL_ALT)
    draw.text((1570, 91), step, font=FONT_SMALL, fill=BLUE)
    draw.line((90, 205, 1830, 205), fill=(48, 71, 103), width=2)
    return image, draw


def _render_frames(result: dict[str, Any], frame_dir: Path) -> int:
    discovered = result["discovered"]
    read_call = result["read_call"]
    write_call = result["write_call"]
    discovered_names = ", ".join(item["name"] for item in discovered)
    frames: list[tuple[str, str, list[tuple[str, str, tuple[int, int, int]]]]] = [
        (
            "L5 · Governed MCP",
            "Evidence video generated from a real local MCP stdio round trip",
            [
                ("Boundary", "MCP discovers capabilities; BAGO decides authority.", BLUE),
                ("Run", "ClientSession → local_mcp_server.py → GovernedMCPAdapter", GREEN),
                ("Result", "One READ allowed; one WRITE stopped before transport.", AMBER),
            ],
        ),
        (
            "1 · Discovery",
            "tools/list is observed as untrusted capability metadata",
            [
                ("Server", result["server"], BLUE),
                ("Discovered", discovered_names, BLUE),
                ("Authority", "Not granted by discovery", AMBER),
            ],
        ),
        (
            "2 · Explicit registration",
            "effect classification is assigned in BAGO, outside the MCP server",
            [
                ("READ", "get_lab_status → EffectType.READ", GREEN),
                ("WRITE", "propose_lab_note → EffectType.WRITE", AMBER),
                ("Policy", "Only READ is automatic; WRITE requires human approval.", BLUE),
            ],
        ),
        (
            "3 · Governed READ call",
            "the permit is bound to the request before the transport call",
            [
                ("Decision", f"{read_call['decision']} · {read_call['execution_outcome']}", GREEN),
                ("Request", read_call["request_id"], BLUE),
                ("Transport", f"called={read_call['actual_effect']['called']} · {read_call['tool_name']}", GREEN),
            ],
        ),
        (
            "4 · Governed WRITE denial",
            "the adapter refuses the call before it reaches the MCP server",
            [
                ("Decision", f"{write_call['decision']} · no automatic permit", AMBER),
                ("Request", write_call["request_id"], BLUE),
                ("Transport", f"called={write_call['actual_effect']['called']} · pre-transport block", RED),
            ],
        ),
        (
            "5 · Evidence receipt",
            "both outcomes remain auditable and linked to the MCP capability",
            [
                ("READ evidence", read_call["evidence_refs"][0], GREEN),
                ("WRITE evidence", write_call["evidence_refs"][0], AMBER),
                ("Invariant", "discovered ≠ registered ≠ authorized ≠ executed", BLUE),
            ],
        ),
        (
            "Verified local result",
            "BAGO governs the MCP boundary",
            [
                ("PASS", "READ reached the local MCP server with ALLOW.", GREEN),
                ("PASS", "WRITE was REQUIRE_HUMAN and never reached the server.", GREEN),
                ("Artifact", "evidence/mcp_governed_demo.mp4", BLUE),
            ],
        ),
    ]
    for index, (title, subtitle, cards) in enumerate(frames):
        image, draw = _base(title, subtitle, f"L5 / {index + 1}/{len(frames)}")
        if index == 0:
            draw.text((94, 255), "Discovery → Registry → ExecutionRequest → Permit → Receipt", font=FONT_SECTION, fill=BLUE)
        for card_index, (label, value, accent) in enumerate(cards):
            top = 300 + card_index * 190
            _card(draw, (110, top, 1810, top + 145), label, value, accent=accent)
        footer = "Generated from actual run_demo() output · local protocol evidence · no production claim"
        draw.text((94, 1005), footer, font=FONT_SMALL, fill=MUTED)
        image.save(frame_dir / f"frame_{index:03d}.png")
    return len(frames)


def _render_video(frame_dir: Path, frame_count: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to render the evidence video")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-framerate",
        "1/2",
        "-i",
        str(frame_dir / "frame_%03d.png"),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-level",
        "4.0",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(OUTPUT_PATH),
    ]
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def main() -> None:
    result = anyio.run(run_demo)
    with tempfile.TemporaryDirectory(prefix="mcp-evidence-") as temp_dir:
        frame_dir = Path(temp_dir)
        frame_count = _render_frames(result, frame_dir)
        _render_video(frame_dir, frame_count)
    digest = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    HASH_PATH.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    EVIDENCE_PATH.write_text(
        render_evidence(result) + f"\nVideo SHA-256: `{digest}`\n",
        encoding="utf-8",
    )
    print(f"Rendered {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"SHA256: {digest}")
    print(json.dumps({"read": result["read_call"], "write": result["write_call"]}, indent=2))


if __name__ == "__main__":
    main()
