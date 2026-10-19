from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from capture_dummy_manual import install_mock
from record_current_ui_tutorial import install_demo_api


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "agent-chat-control" / "assets" / "manual-ui-actual-2026-10-19"
BASE = "http://127.0.0.1:5173"


def capture(page, filename: str) -> None:
    page.screenshot(path=str(OUT / filename), full_page=True, animations="disabled")
    print(filename, flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        page = context.new_page()
        install_mock(page)
        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("main", name="Chat view").wait_for()
        page.wait_for_timeout(400)
        capture(page, "01-chat.png")

        interaction = page.get_by_role("navigation", name="Interaction layer")
        for label, filename in [
            ("Workspace", "02-workspace.png"),
            ("Capabilities", "03-capabilities.png"),
            ("Agent Builder", "04-agent-builder.png"),
            ("Agent Runs", "05-agent-runs.png"),
            ("Agent Evaluation Lab", "06-evaluation-lab.png"),
        ]:
            interaction.get_by_role("button", name=label).click()
            page.wait_for_timeout(300)
            capture(page, filename)

        page.get_by_role("button", name="Open Inspect").click()
        views = page.get_by_role("navigation", name="Data views")
        for label, filename in [
            ("Decision Inspector", "07-decision-inspector.png"),
            ("Job History", "08-job-history.png"),
            ("Summary", "09-summary.png"),
            ("Retrieval & Ontology", "10-retrieval-ontology.png"),
            ("Authorization", "11-authorization.png"),
            ("Trace", "12-trace.png"),
            ("Evaluation", "13-evaluation.png"),
        ]:
            views.get_by_role("button", name=label).click()
            page.wait_for_timeout(250)
            capture(page, filename)

        page.get_by_role("button", name="Back to Workspace").click()
        page.get_by_role("button", name="Open settings").click()
        page.wait_for_timeout(250)
        capture(page, "14-provider-models.png")
        page.get_by_role("navigation", name="Settings sections").get_by_role("button", name="Cognition & context").click()
        page.wait_for_timeout(250)
        capture(page, "15-cognition-context.png")

        # Capture the orchestrator's inline workflows with isolated synthetic API state.
        for prompt, filename, expected in [
            ("Enséñame el historial de jobs", "16-chat-job-history-inline.png", "table"),
            ("Quiero crear un agente para responder preguntas sobre pedidos", "17-chat-agent-draft-inline.png", "Configure Agent"),
            ("Abre Workspace", "18-chat-confirm-screen-change.png", "Confirm screen change"),
        ]:
            chat = context.new_page()
            install_demo_api(chat)
            chat.goto(BASE, wait_until="networkidle")
            chat.get_by_role("main", name="Chat view").wait_for()
            chat.get_by_label("Message the assistant or selected agent").fill(prompt)
            chat.get_by_role("button", name="Send").click()
            if expected == "table":
                chat.get_by_role("table").wait_for()
            elif expected == "Configure Agent":
                chat.get_by_role("heading", name="Configure Agent").wait_for()
            else:
                chat.get_by_role("region", name=expected).wait_for()
            chat.wait_for_timeout(250)
            capture(chat, filename)
            chat.close()
        browser.close()


if __name__ == "__main__":
    main()
