"""Read-only local HTTP smoke; no registration writes or provider inference."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {"src", "href"} and value and value.startswith("/assets/"):
                self.paths.add(value)


root = Path.cwd()
url = "http://127.0.0.1:8080"
health = requests.get(url + "/api/health", timeout=10)
providers = requests.get(url + "/api/providers/available", timeout=10)
page = requests.get(url + "/", timeout=10)
parser = Assets()
parser.feed(page.text)
entries = [{key: item.get(key) for key in ("provider_id", "state", "runtime_support")}
           for item in providers.json().get("providers", [])
           if item.get("provider_id") in {"openai-platform", "github-copilot"}]
result = {
    "checked_at": datetime.now(timezone.utc).isoformat(), "url": url,
    "health_status": health.status_code, "health": health.json(),
    "provider_status": providers.status_code, "providers": entries,
    "frontend_status": page.status_code,
    "served_html_matches_build": hashlib.sha256(page.content).digest() == hashlib.sha256((root / "frontend/dist/index.html").read_bytes()).digest(),
    "assets": {asset: requests.get(url + asset, timeout=10).status_code for asset in sorted(parser.paths)},
    "live_inference": "NOT_RUN", "browser_visual": "NOT_RUN - no connected browser",
}
target = Path(__file__).resolve().parent.parent / "evidence/runtime.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
assert health.status_code == providers.status_code == page.status_code == 200
assert result["served_html_matches_build"] and result["assets"] and all(status == 200 for status in result["assets"].values())
assert len(entries) == 2 and all(entry["runtime_support"] == "chat_and_agent_runner" for entry in entries)
