"""Read-only protocol probe: connect, send no execution payload, observe fail-closed response."""

from __future__ import annotations

import asyncio
import json
from urllib.request import urlopen

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus


BASE = "http://127.0.0.1:8084"
WS_URL = "ws://127.0.0.1:8084/ws/agents/run"
ORIGIN = "http://127.0.0.1:8084"


def current_jobs() -> dict:
    with urlopen(f"{BASE}/api/jobs/list", timeout=5) as response:
        return json.load(response)


async def main() -> None:
    before = current_jobs()
    same_origin = None
    try:
        async with connect(WS_URL, origin=ORIGIN, open_timeout=5, close_timeout=3):
            same_origin = {"accepted": True, "handshake_status": 101}
    except InvalidStatus as rejected:
        same_origin = {
            "accepted": False,
            "handshake_status": rejected.response.status_code,
        }

    # The server's compiled allowlist includes the default local API origin.
    # Connect without sending any agent/job payload to observe the endpoint's fail-closed frame.
    async with connect(WS_URL, origin="http://127.0.0.1:8080", open_timeout=5, close_timeout=3) as socket:
        allowed_origin_handshake = socket.response.status_code
        frame_text = await asyncio.wait_for(socket.recv(), timeout=5)
        try:
            await asyncio.wait_for(socket.recv(), timeout=5)
            close_code = None
            close_reason = None
        except ConnectionClosed as closed:
            close_code = closed.code
            close_reason = closed.reason
    after = current_jobs()

    message = json.loads(frame_text)
    before_jobs = before.get("jobs", [])
    after_jobs = after.get("jobs", [])
    result = {
        "websocket_url": WS_URL,
        "origin": ORIGIN,
        "app_origin_probe": same_origin,
        "approved_origin_probe": {
            "origin": "http://127.0.0.1:8080",
            "handshake_status": allowed_origin_handshake,
        },
        "client_payload_sent": False,
        "server_message": message,
        "close_code": close_code,
        "close_reason": close_reason,
        "jobs_before_count": len(before_jobs),
        "jobs_after_count": len(after_jobs),
        "job_ids_before": [job.get("job_id") for job in before_jobs],
        "job_ids_after": [job.get("job_id") for job in after_jobs],
        "job_list_unchanged": before_jobs == after_jobs,
        "expected_behavior": (
            allowed_origin_handshake == 101
            and message.get("code") == "execution_unavailable"
            and close_code == 1008
            and before_jobs == after_jobs
        ),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result["expected_behavior"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
