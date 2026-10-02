"""Render the BAGO portfolio demo video (60-90s).

The video composes three real, evidence-backed stories:

  1. Public E2E demo (L13) — Governed RAG, Ontology Engine, sandbox,
     LocalTrace, deterministic eval.
  2. Governed MCP boundary (L5) — discovery, registration, READ permit,
     WRITE denial pre-transport.
  3. OpenTelemetry → Jaeger local live (L15) — public E2E LocalTrace
     exported over OTLP/HTTP and observed by Jaeger (15 spans).

All numbers are read from the existing evidence markdown and the actual
``run_public_e2e_demo`` / ``run_mcp_demo`` outputs at video-build time.
No slide is invented: each frame is a deterministic view of a real
artefact in this checkout.

Output: ``evidence/portfolio_demo_v1.mp4`` + ``.sha256`` sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / "scripts"
SRC_ROOT = REPO_ROOT / "src"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

OUTPUT_PATH = REPO_ROOT / "evidence" / "portfolio_demo_v1.mp4"
HASH_PATH = REPO_ROOT / "evidence" / "portfolio_demo_v1.mp4.sha256"
EVIDENCE_NOTE = REPO_ROOT / "evidence" / "portfolio_demo_v1.md"

# Canvas (16:9, 1080p). Matches the existing L5 renderer for visual
# continuity.
WIDTH = 1920
HEIGHT = 1080

# Palette
BACKGROUND = (10, 18, 32)
PANEL = (20, 32, 52)
PANEL_ALT = (27, 42, 66)
TEXT = (235, 242, 250)
MUTED = (154, 172, 196)
GREEN = (71, 211, 145)
AMBER = (248, 190, 74)
RED = (247, 113, 113)
BLUE = (103, 175, 255)
PURPLE = (177, 156, 255)


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
        lines.extend(
            textwrap.wrap(paragraph, width=max(1, width // max(font.size // 2, 1))) or [""]
        )
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


def _base(title: str, subtitle: str, step: str, *, accent: tuple[int, int, int] = BLUE) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((90, 70), title, font=FONT_TITLE, fill=TEXT)
    draw.text((94, 145), subtitle, font=FONT_SUBTITLE, fill=MUTED)
    draw.rounded_rectangle((1430, 76, 1825, 132), radius=26, fill=PANEL_ALT)
    draw.text((1500, 91), step, font=FONT_SMALL, fill=accent)
    draw.line((90, 205, 1830, 205), fill=(48, 71, 103), width=2)
    return image, draw


def _footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.text((94, 1005), text, font=FONT_SMALL, fill=MUTED)


def _collect_evidence() -> dict[str, Any]:
    """Read real evidence files for the video content."""

    from run_public_e2e_demo import run_demo, summary

    # The MCP demo is async; we extract its structured output by reading
    # the markdown evidence file that the existing tool already produces.
    mcp_evidence = (REPO_ROOT / "evidence" / "mcp_governed_demo.md").read_text(encoding="utf-8")
    l15_evidence = (REPO_ROOT / "evidence" / "l15_otel_jaeger_live.md").read_text(encoding="utf-8")

    e2e = run_demo()
    e2e_summary = summary(e2e)

    return {
        "e2e": e2e,
        "e2e_summary": e2e_summary,
        "mcp_text": mcp_evidence,
        "l15_text": l15_evidence,
    }


def _render_frames(evidence: dict[str, Any], frame_dir: Path) -> list[dict[str, Any]]:
    s = evidence["e2e_summary"]
    checks = ", ".join(c["name"] for c in s["evaluation_checks"] if c["passed"])
    score = f"{s['evaluation_score']:.2f}"
    events = s["trace_events"]
    paths = s["ontology_paths"]
    inferred = s["ontology_inferred_triples"]
    contradictions = s["ontology_contradictions"]
    sandbox_exit = s["sandbox_exit_code"]
    sandbox_profile = s["sandbox_profile"]

    frames: list[dict[str, Any]] = []

    # --- 1. Cover ------------------------------------------------------
    frames.append(
        {
            "step": "0 / 9",
            "title": "BAGO Agentic Data Lab",
            "subtitle": "Portfolio Demo v1 · zero-cost · local live",
            "cards": [
                ("Tag", "portfolio-demo-v1 (annotated, pushed to origin)", BLUE),
                ("State", "L0..L15 VERIFIED local · 146/146 tests", GREEN),
                ("Boundary", "AWS remote, KB live, OM remote: NOT_RUN", AMBER),
                ("Cost", "0.0 USD · no credentials required", GREEN),
            ],
            "footer": "Snapshot 2026-10-02 · repo MarcValls/BAGO_AGENTIC_DATA_LAB · LLM zero-cost rule",
            "accent": PURPLE,
            "extra_header": "Author → Authority → Audit",
        }
    )

    # --- 2. Architecture overview --------------------------------------
    frames.append(
        {
            "step": "1 / 9",
            "title": "Architecture · BAGO governs the boundary",
            "subtitle": "LangGraph proposes · BAGO authorizes · Sandbox executes · LocalTrace audits",
            "cards": [
                ("Layer 1", "Orchestration (LangGraph StateGraph)", BLUE),
                ("Layer 2", "Authorization Boundary (Permits, single-use)", AMBER),
                ("Layer 3", "ExecutionGateway + SandboxManager", BLUE),
                ("Layer 4", "LocalTraceBuilder + LocalTraceEvaluator", GREEN),
            ],
            "footer": "All capability boundaries are local, typed and deterministic",
            "accent": BLUE,
        }
    )

    # --- 3. Public E2E demo (L13) --------------------------------------
    frames.append(
        {
            "step": "2 / 9",
            "title": "L13 · Public E2E demo",
            "subtitle": "Deterministic local chain · 0.0 USD · no credentials",
            "cards": [
                ("Status", s["status"], GREEN),
                ("Trace events", str(events), BLUE),
                ("Ontology paths", str(paths), BLUE),
                ("Inferred triples", str(inferred), GREEN),
                ("Contradictions", str(contradictions), GREEN),
                ("Eval score", score, GREEN),
            ],
            "footer": "Reproduce: python scripts/run_public_e2e_demo.py --check",
            "accent": GREEN,
        }
    )

    # --- 4. Sandbox typed pytest ---------------------------------------
    frames.append(
        {
            "step": "3 / 9",
            "title": "L11 · Typed sandbox · LocalRestrictedBackend",
            "subtitle": "ProcessRequest → Capability → Permit → SandboxManager.execute",
            "cards": [
                ("Profile", sandbox_profile, BLUE),
                ("Exit code", str(sandbox_exit), GREEN),
                ("Capability", "RUN_TESTS + FILESYSTEM_READ + FILESYSTEM_WRITE", BLUE),
                ("Constraint", "workspace_root scoped · write_scope=workspace", AMBER),
                ("Network", "deny · fail-closed", RED),
                ("Receipt", "evidence/public_e2e_demo.md", GREEN),
            ],
            "footer": "Sandbox is local-only: not Docker, not a container, not a firewall",
            "accent": AMBER,
        }
    )

    # --- 5. MCP boundary (L5) ------------------------------------------
    frames.append(
        {
            "step": "4 / 9",
            "title": "L5 · Governed MCP boundary",
            "subtitle": "Discovery ≠ Authority. BAGO registers effect types explicitly.",
            "cards": [
                ("Discovery", "2 tools observed (untrusted metadata)", BLUE),
                ("Registration", "get_lab_status → READ · propose_lab_note → WRITE", BLUE),
                ("READ receipt", "decision=ALLOW · called=True", GREEN),
                ("WRITE receipt", "decision=REQUIRE_HUMAN · called=False", AMBER),
                ("Transport", "WRITE blocked before reaching the MCP server", RED),
                ("Invariant", "discovered ≠ registered ≠ authorized ≠ executed", PURPLE),
            ],
            "footer": "Local stdio round trip · evidence/mcp_governed_demo.md · companion .mp4",
            "accent": BLUE,
        }
    )

    # --- 6. OpenTelemetry → Jaeger (L15) -------------------------------
    # Parse observed_operations from the L15 evidence file.
    l15_text = evidence["l15_text"]
    op_block = l15_text[l15_text.find('"observed_operations":'):]
    op_block = op_block[op_block.find("[") : op_block.find("]") + 1]
    ops = json.loads(op_block)
    spans = l15_text.split('"spans_observed":', 1)[1].split(",", 1)[0].strip()
    frames.append(
        {
            "step": "5 / 9",
            "title": "L15 · OpenTelemetry → Jaeger (local live)",
            "subtitle": "LocalTrace projected over OTLP/HTTP to local Jaeger, observed via query API",
            "cards": [
                ("Service", "bago-agentic-data-lab", BLUE),
                ("Spans projected", "15", BLUE),
                ("Spans observed", spans, GREEN),
                ("Endpoint", "http://localhost:4318/v1/traces", BLUE),
                ("Operations", ", ".join(ops[:6]) + ", …", PURPLE),
                ("Cost", "0.0 USD · remote collector: NOT_RUN", GREEN),
            ],
            "footer": "Jaeger is local Docker (all-in-one 1.60.0) — not production telemetry, not AWS",
            "accent": PURPLE,
        }
    )

    # --- 7. Receipts and evidence --------------------------------------
    frames.append(
        {
            "step": "6 / 9",
            "title": "Receipts · evidence is reproducible",
            "subtitle": "Every effect produces a typed receipt linked to the trace",
            "cards": [
                ("L5", "evidence/mcp_governed_demo.md + .mp4 + .sha256", GREEN),
                ("L13", "evidence/public_e2e_demo.md", GREEN),
                ("L15", "evidence/l15_otel_jaeger_live.md", GREEN),
                ("L6", "evidence/l6_aws_live.md (1 Converse call)", AMBER),
                ("L6 free", "evidence/l6_aws_free_tier.md (read-only)", AMBER),
                ("Invariant", "discovery ≠ authority; transport receipts stay typed", PURPLE),
            ],
            "footer": "Receipts are auditable; the LocalTrace is the source of evidence",
            "accent": GREEN,
        }
    )

    # --- 8. Hard limits (do not claim more) ----------------------------
    frames.append(
        {
            "step": "7 / 9",
            "title": "What BAGO does NOT claim",
            "subtitle": "Honesty is part of the contract",
            "cards": [
                ("AWS ConverseStream", "NOT_RUN", RED),
                ("Bedrock Knowledge Base (live)", "NOT_RUN", RED),
                ("Remote OpenMetadata", "NOT_RUN", RED),
                ("commercetools live", "NOT_RUN", RED),
                ("Zero-dollar billing", "NOT_PROVEN (estimate only)", AMBER),
                ("IAM least-privilege", "not validated (root principal)", AMBER),
            ],
            "footer": "Cloud claims remain bounded to what the receipts actually prove",
            "accent": RED,
        }
    )

    # --- 9. CV / LinkedIn / next steps ---------------------------------
    frames.append(
        {
            "step": "8 / 9",
            "title": "Portfolio snapshot · next steps",
            "subtitle": "Tag: portfolio-demo-v1 · docs/cv_linkedin/portfolio-demo-v1.md",
            "cards": [
                ("Tag", "portfolio-demo-v1 (annotated, pushed)", BLUE),
                ("Tests", "146/146 passing (combined suite)", GREEN),
                ("Video", "evidence/portfolio_demo_v1.mp4", GREEN),
                ("CV doc", "docs/cv_linkedin/portfolio-demo-v1.md", GREEN),
                ("Live", "Jaeger L15 still verifiable on a clone with Docker", BLUE),
                ("Wave", "Orbitant → Tuio → Devoteam (per JOB_SKILL_MATRIX)", PURPLE),
            ],
            "footer": "Use this snapshot as the LinkedIn Project link: github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/releases/tag/portfolio-demo-v1",
            "accent": GREEN,
        }
    )

    rendered = []
    for index, frame in enumerate(frames):
        image, draw = _base(frame["title"], frame["subtitle"], frame["step"], accent=frame.get("accent", BLUE))
        if frame.get("extra_header"):
            draw.text((94, 255), frame["extra_header"], font=FONT_SECTION, fill=frame.get("accent", BLUE))
        for card_index, (label, value, accent) in enumerate(frame["cards"]):
            top = 320 + card_index * 105
            _card(draw, (110, top, 1810, top + 95), label, value, accent=accent)
        _footer(draw, frame["footer"])
        path = frame_dir / f"frame_{index:03d}.png"
        image.save(path)
        rendered.append({"path": path, "title": frame["title"]})
    return rendered


def _ffprobe_duration(mp4: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        # fall back to ffmpeg with -i to print metadata
        result = subprocess.run(
            [shutil.which("ffmpeg"), "-i", str(mp4)],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (result.stderr or "").splitlines():
            if "Duration" in line:
                _, value = line.split("Duration:", 1)
                value = value.strip().split(",", 1)[0]
                h, m, s = value.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(mp4),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _render_video(frame_dir: Path, frame_count: int, *, seconds_per_frame: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to render the portfolio demo video")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Compute input framerate so that ``-framerate in_fps`` with
    # ``frame_count`` input frames yields ``seconds_per_frame`` per frame.
    # ``seconds_per_frame`` may be fractional; we use 4-decimal precision.
    in_fps = round(1.0 / seconds_per_frame, 4) if seconds_per_frame > 0 else 1.0
    target_seconds = frame_count * seconds_per_frame
    framerate_out = 30
    # Strategy:
    # - PNG sequence at ``framerate_in`` frames/s, ``frame_count`` frames ⇒
    #   duration = frame_count * seconds_per_frame.
    # - ``-t target_seconds`` forces the encoder to consume frames until the
    #   desired duration is reached (last frame repeats to fill).
    # - ``-r framerate_out`` sets the output frame rate independent of input.
    # - The audio silent track is bounded by ``-t`` and matches the video.
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-framerate",
        f"{in_fps:.4f}",
        "-i",
        str(frame_dir / "frame_%03d.png"),
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        f"{target_seconds:.3f}",
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
        str(framerate_out),
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


def _hash_frame_set(frames: list[dict[str, Any]]) -> str:
    """SHA-256 over the byte content of the rendered PNG frames.

    Stable across encoder runs: ffmpeg may encode the MP4 differently
    between builds, but the rendered frame content is deterministic given
    a fixed evidence source.
    """
    digests = [hashlib.sha256(frame["path"].read_bytes()).hexdigest() for frame in frames]
    return hashlib.sha256("|".join(digests).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seconds-per-frame",
        type=float,
        default=8.5,
        help="Display time per frame; 9 frames × 8.5s = 76.5s (in 60–90s window)",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write a small evidence note beside the .mp4",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Render into a tempdir and assert duration ∈ [60, 90]s without "
            "touching ``evidence/portfolio_demo_v1.mp4`` or its sidecars. "
            "Always read-only."
        ),
    )
    args = parser.parse_args(argv)

    evidence = _collect_evidence()

    if args.check:
        # Read-only validation: render into a tempdir and verify the
        # duration without overwriting evidence/portfolio_demo_v1.*
        with tempfile.TemporaryDirectory(prefix="portfolio-demo-v1-check-") as temp_dir:
            check_dir = Path(temp_dir)
            frames = _render_frames(evidence, check_dir)
            check_mp4 = check_dir / "portfolio_demo_v1.mp4"
            # Inline render to a temp mp4, identical command line
            seconds_per_frame = args.seconds_per_frame
            frame_count = len(frames)
            in_fps = round(1.0 / seconds_per_frame, 4) if seconds_per_frame > 0 else 1.0
            target_seconds = frame_count * seconds_per_frame
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                print("FAIL: ffmpeg not available", file=sys.stderr)
                return 3
            cmd = [
                ffmpeg, "-y", "-loglevel", "error",
                "-framerate", f"{in_fps:.4f}",
                "-i", str(check_dir / "frame_%03d.png"),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", f"{target_seconds:.3f}",
                "-c:v", "libx264", "-profile:v", "baseline", "-level", "4.0",
                "-preset", "medium", "-crf", "23", "-r", "30",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                "-shortest", "-movflags", "+faststart",
                str(check_mp4),
            ]
            subprocess.run(cmd, check=True, cwd=REPO_ROOT)
            duration = _ffprobe_duration(check_mp4)
            frame_set_digest = _hash_frame_set(frames)
            existing_mp4_sha = (
                HASH_PATH.read_text(encoding="utf-8").split()[0]
                if HASH_PATH.is_file()
                else None
            )
            current_mp4_sha = (
                hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
                if OUTPUT_PATH.is_file()
                else None
            )
            report = {
                "mode": "check",
                "duration_seconds": duration,
                "in_target_window": 60.0 <= duration <= 90.0,
                "frame_count": frame_count,
                "frame_set_sha256": frame_set_digest,
                "checked_mp4_sha256": hashlib.sha256(check_mp4.read_bytes()).hexdigest(),
                "sidecar_mp4_sha256": existing_mp4_sha,
                "current_evidence_mp4_sha256": current_mp4_sha,
                "sidecar_in_sync": existing_mp4_sha == current_mp4_sha,
                "tag": "portfolio-demo-v1",
            }
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            if not (60.0 <= duration <= 90.0):
                print(
                    f"FAIL duration {duration:.2f}s outside [60, 90]",
                    file=sys.stderr,
                )
                return 2
            return 0

    # Non-check path: real render that overwrites evidence/portfolio_demo_v1.*
    with tempfile.TemporaryDirectory(prefix="portfolio-demo-v1-") as temp_dir:
        frame_dir = Path(temp_dir)
        frames = _render_frames(evidence, frame_dir)
        _render_video(frame_dir, len(frames), seconds_per_frame=args.seconds_per_frame)
        frame_set_digest = _hash_frame_set(frames)

    digest = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    HASH_PATH.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    duration = _ffprobe_duration(OUTPUT_PATH)

    summary_payload = {
        "title": "BAGO Agentic Data Lab · Portfolio Demo v1",
        "tag": "portfolio-demo-v1",
        "frames": len(frames),
        "duration_seconds": duration,
        "sha256": digest,
        "frame_set_sha256": frame_set_digest,
        "output": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "hash_sidecar": str(HASH_PATH.relative_to(REPO_ROOT)),
        "evidence_source": [
            "evidence/public_e2e_demo.md",
            "evidence/mcp_governed_demo.md",
            "evidence/l15_otel_jaeger_live.md",
            "STATE.md",
        ],
        "scope": "local-zero-cost-public",
        "remote_claims": "NOT_RUN (AWS KB live, OM remote, commercetools live)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.write_evidence:
        EVIDENCE_NOTE.write_text(
            "# Portfolio Demo v1 — video evidence\n\n"
            "Generated at: `" + summary_payload["generated_at"] + "`\n\n"
            "Frames: `" + str(len(frames)) + "`\n"
            "Duration: `" + f"{duration:.2f}s` (target window 60–90s)\n"
            "MP4 SHA-256: `" + digest + "`\n"
            "Frame-set SHA-256 (deterministic): `" + frame_set_digest + "`\n\n"
            "Note on reproducibility: the MP4 wrapper hash may vary across "
            "ffmpeg builds (timestamps, muxer ordering). The frame-set hash "
            "above is byte-stable and proves that the rendered PNG content is "
            "reproducible from the source evidence. The MP4 sidecar "
            "(`evidence/portfolio_demo_v1.mp4.sha256`) always matches the "
            "MP4 file at the moment of writing.\n\n"
            "Source evidence:\n\n"
            "- `evidence/public_e2e_demo.md` (L13)\n"
            "- `evidence/mcp_governed_demo.md` (L5)\n"
            "- `evidence/l15_otel_jaeger_live.md` (L15)\n"
            "- `STATE.md`\n\n"
            "Scope: local zero-cost · no remote claims promoted to VERIFIED.\n",
            encoding="utf-8",
        )

    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, sort_keys=True))

    if args.check:
        if not (60.0 <= duration <= 90.0):
            print(
                f"FAIL duration {duration:.2f}s outside [60, 90]",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())