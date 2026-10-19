from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Route, sync_playwright
from capture_dummy_manual import response_for as manual_demo_response


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5173"
ASSETS = ROOT / "docs" / "agent-chat-control" / "assets"
OUTPUT = ASSETS / "ADL_videotutorial_ui_actual_2026-10-19.mp4"
SUBTITLES = ASSETS / "ADL_videotutorial_ui_actual_2026-10-19.es.srt"
VOICE_DIR = ASSETS / "narration" / "ui-actual-2026-10-19"
JOBS = [{
    "job_id": "job_demo_593e2eb6", "agent_id": None, "job_type": "demo",
    "status": "success", "created_at": "2026-10-19T12:54:02Z",
    "completed_at": "2026-10-19T12:54:06Z", "duration_ms": 4190,
    "exit_code": 0, "stdout": "Resultado sintético de demostración", "stderr": "",
    "cost_usd": 0.0, "metrics": {},
}]
AGENT_DRAFT = {
    "name": "Agente de soporte demo",
    "description": "Responde preguntas sobre pedidos ficticios.",
    "type": "rag",
    "system_prompt": "Responde solo con los datos de demostración proporcionados.",
    "tools": ["retrieval.search"],
    "provider_id": "ollama-cloud",
    "model_id": "qwen3:8b",
    "retrieval_config": {"mode": "hybrid", "top_k": 5},
}

SCENES = [
    {
        "action": "intro",
        "narration": "Esta es la interfaz actual de BAGO. El chat orquestador es el punto de partida: pide ayuda con tus palabras.",
    },
    {
        "action": "jobs",
        "narration": "Pide el historial de trabajos y la tabla aparece en el chat. Los datos de este vídeo son sintéticos.",
    },
    {
        "action": "draft",
        "narration": "Describe el agente que quieres. Revisa el borrador editable; solo se crea cuando confirmas.",
    },
    {
        "action": "workspace_confirm",
        "narration": "Para abrir otra zona, pídelo en el chat. BAGO muestra el destino y espera tu confirmación.",
    },
    {
        "action": "workspace",
        "narration": "Workspace reúne la carpeta elegida y las capas de contexto del proyecto.",
    },
    {
        "action": "builder_confirm",
        "narration": "Pide abrir Agent Builder y confirma el cambio para llegar al formulario completo.",
    },
    {
        "action": "builder",
        "narration": "Completa los datos del agente y usa Preview para revisarlos. En este vídeo no guardamos nada.",
    },
    {
        "action": "settings",
        "narration": "Settings reúne proveedores, modelos y contexto. No se modifican credenciales ni preferencias.",
    },
    {
        "action": "finish",
        "narration": "Lo que ves es demostrativo: no hay trabajos ni agentes reales en esta grabación.",
    },
]


def conversation_summary() -> dict:
    return {
        "id": "conv_demo_current_ui",
        "owner_kind": "assistant",
        "owner_id": "app-assistant",
        "title": "Recorrido de demostración",
        "status": "active",
        "updated_at": "2026-10-19T13:00:00Z",
        "revision": 0,
        "messages": [],
    }


def fulfill(route: Route, body: dict, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body, ensure_ascii=False),
    )


def install_demo_api(page) -> None:
    state: dict = {"conversation": None}

    def handle(route: Route) -> None:
        request = route.request
        path = urlparse(request.url).path
        method = request.method.upper()
        payload = request.post_data_json if request.post_data else {}
        conv = state["conversation"]

        if path == "/api/conversations" and method == "POST":
            conv = conversation_summary()
            state["conversation"] = conv
            fulfill(route, {key: value for key, value in conv.items() if key != "messages"})
            return
        if path == "/api/conversations" and method == "GET":
            items = [] if conv is None else [{key: value for key, value in conv.items() if key != "messages"}]
            fulfill(route, {"conversations": items})
            return
        if path.startswith("/api/conversations/") and method == "GET":
            fulfill(route, conv or {}, status=200 if conv else 404)
            return
        if path == "/api/chat/control" and method == "POST":
            if conv is None:
                fulfill(route, {"detail": "No demo conversation is active."}, status=409)
                return
            text = str(payload.get("message", ""))
            folded = text.casefold()
            if "historial" in folded or "jobs" in folded or "trabajos" in folded:
                operation = "job_history"
                assistant_message = "Aquí tienes el historial de trabajos de demostración."
                extra = {}
            elif "agente" in folded and any(word in folded for word in ("crear", "diseñar", "disen", "quiero")):
                operation = "draft_agent"
                assistant_message = "Revisa este borrador de demostración. No se guardará en este recorrido."
                extra = {"agent_draft": AGENT_DRAFT, "created": False}
            elif "workspace" in folded:
                operation = "confirm_navigation"
                assistant_message = "¿Quieres cambiar de pantalla?"
                extra = {"navigation": {"view": "workspace"}}
            elif "agent builder" in folded:
                operation = "confirm_navigation"
                assistant_message = "¿Quieres cambiar de pantalla?"
                extra = {"navigation": {"view": "builder"}}
            else:
                operation = "chat"
                assistant_message = "Respuesta sintética de demostración."
                extra = {}

            conv["messages"].extend([
                {"id": f"demo-user-{conv['revision'] + 1}", "role": "user", "content": text},
                {"id": f"demo-assistant-{conv['revision'] + 2}", "role": "assistant", "content": assistant_message},
            ])
            conv["revision"] += 2
            conv["updated_at"] = "2026-10-19T13:00:00Z"
            fulfill(route, {
                "operation": operation,
                "assistant_message": assistant_message,
                "conversation_id": conv["id"],
                "revision": conv["revision"],
                "conversation": conv,
                **extra,
            })
            return
        if path == "/api/jobs/list":
            fulfill(route, {"jobs": JOBS})
            return
        if path == "/api/agents/list":
            fulfill(route, {"agents": []})
            return
        if path == "/api/chat/context":
            fulfill(route, {
                "workspace_root": "C:/proyecto-demo",
                "cognition": {"profile": "BAGO5_CHAT_COGNITION_V0.1", "capacity": 6, "max_hops": 2},
                "memory": {"kind": "local", "state": "present", "description": "Fuente sintética"},
                "paths": [{"id": "project", "label": "Contexto del proyecto", "path": "docs/ejemplo.md", "state": "present", "kind": "file", "purpose": "Dato sintético para el vídeo."}],
            })
            return
        if path == "/api/providers/ollama/status":
            fulfill(route, {"provider_id": "ollama-cloud", "state": "not_configured", "runtime_mode": "host", "auth_mode": "none", "model_id": None})
            return
        if path == "/api/providers/ollama/models":
            fulfill(route, {"models": [], "source": "demo"})
            return
        if path == "/api/artifacts":
            fulfill(route, manual_demo_response(request.url, method))
            return
        fulfill(route, {})

    page.route("**/api/**", handle)


def click_navigation(page, label: str) -> None:
    page.get_by_role("navigation", name="Interaction layer").get_by_role("button", name=label).click()


def perform_action(page, action: str) -> None:
    if action == "intro":
        page.get_by_role("main", name="Chat view").wait_for()
        return
    if action in {"jobs", "draft", "workspace_confirm", "builder_confirm"}:
        if action == "builder_confirm":
            click_navigation(page, "Chat")
        prompts = {
            "jobs": "Enséñame el historial de jobs",
            "draft": "Quiero crear un agente para responder preguntas sobre pedidos",
            "workspace_confirm": "Abre Workspace",
            "builder_confirm": "Abre Agent Builder",
        }
        composer = page.get_by_label("Message the assistant or selected agent")
        composer.fill(prompts[action])
        page.get_by_role("button", name="Send").click()
        if action == "jobs":
            page.get_by_role("table").wait_for()
        elif action == "draft":
            page.get_by_role("heading", name="Configure Agent").wait_for()
        else:
            page.get_by_role("region", name="Confirm screen change").wait_for()
            page.get_by_role("button", name="Sí, cambiar de pantalla").click()
    elif action == "workspace":
        page.get_by_role("main", name="Workspace view").wait_for()
    elif action == "builder":
        page.get_by_role("main", name="Agent Builder view").wait_for()
        page.get_by_role("heading", name="Configure Agent").wait_for()
    elif action == "settings":
        page.get_by_role("button", name="Open settings").click()
        page.get_by_role("dialog").wait_for()
    elif action == "finish":
        page.get_by_role("button", name="Close settings").click()
        click_navigation(page, "Chat")
        page.get_by_role("main", name="Chat view").wait_for()


def narration_files() -> list[Path]:
    paths = [VOICE_DIR / f"scene_{index:02d}.wav" for index in range(len(SCENES))]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing local narration audio: {missing[0]}")
    return paths


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bago-current-ui-tutorial-", dir=ROOT / "output" / "playwright") as work:
        temp_dir = Path(work)
        audio_paths = narration_files()
        audio_durations = [probe_duration(path) for path in audio_paths]
        raw_dir = temp_dir / "raw"
        raw_dir.mkdir()
        timing: list[tuple[float, float]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                device_scale_factor=1,
                record_video_dir=str(raw_dir),
                record_video_size={"width": 1600, "height": 900},
            )
            page = context.new_page()
            page.set_default_timeout(8000)
            install_demo_api(page)
            started = time.monotonic()
            page.goto(BASE, wait_until="networkidle")
            for index, scene in enumerate(SCENES):
                perform_action(page, scene["action"])
                scene_start = time.monotonic() - started
                page.wait_for_timeout(round(audio_durations[index] * 1000) + 350)
                scene_end = scene_start + audio_durations[index]
                timing.append((scene_start, scene_end))
            page_video = page.video
            awaitable_path = None
            context.close()
            awaitable_path = page_video.path()
            browser.close()

        subtitles = []
        for index, (scene, (start, end)) in enumerate(zip(SCENES, timing), start=1):
            subtitles.extend([str(index), f"{srt_timestamp(start)} --> {srt_timestamp(end)}", scene["narration"], ""])
        SUBTITLES.write_text("\n".join(subtitles), encoding="utf-8")

        audio_inputs = ["-i", str(awaitable_path)]
        for audio in audio_paths:
            audio_inputs.extend(["-i", str(audio)])
        filters = []
        mix_labels = []
        for index, ((start, _), _) in enumerate(zip(timing, audio_paths), start=1):
            label = f"a{index}"
            delay = max(0, round(start * 1000))
            filters.append(f"[{index}:a]adelay={delay}|{delay}[{label}]")
            mix_labels.append(f"[{label}]")
        filters.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0[aout]")
        filter_complex = ";".join(filters)
        subtitle_path = str(SUBTITLES).replace("\\", "/").replace(":", "\\:")
        subtitle_filter = f"subtitles=filename='{subtitle_path}':force_style='FontName=Arial,FontSize=15,Outline=1,Shadow=0,Alignment=2,MarginV=30'"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", *audio_inputs,
            "-filter_complex", filter_complex,
            "-vf", subtitle_filter,
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(OUTPUT),
        ], check=True)

    print(json.dumps({
        "video": str(OUTPUT.relative_to(ROOT)),
        "subtitles": str(SUBTITLES.relative_to(ROOT)),
        "duration_seconds": probe_duration(OUTPUT),
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "bytes": OUTPUT.stat().st_size,
        "runtime": BASE,
        "responses": "synthetic, intercepted in the isolated Playwright context",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
