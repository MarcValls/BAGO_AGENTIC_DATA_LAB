from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "brave-browser-mcp"))
import identity as bridge_identity  # noqa: E402


def fake_psutil(monkeypatch, connections=None, executable=None, error=None):
    class AccessDenied(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    def net_connections(kind):
        if error:
            raise error
        return connections or []

    module = SimpleNamespace(
        CONN_LISTEN="LISTEN",
        AccessDenied=AccessDenied,
        NoSuchProcess=NoSuchProcess,
        net_connections=net_connections,
        Process=lambda pid: SimpleNamespace(exe=lambda: executable),
    )
    monkeypatch.setitem(sys.modules, "psutil", module)


def test_chromium_cdp_product_is_verified_by_brave_listener(monkeypatch):
    connection = SimpleNamespace(
        status="LISTEN",
        laddr=SimpleNamespace(port=9222),
        pid=456,
    )
    fake_psutil(
        monkeypatch,
        connections=[connection],
        executable=r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    )

    assert bridge_identity.loopback_listener_is_brave(9222)


def test_chrome_listener_is_not_mistaken_for_brave(monkeypatch):
    connection = SimpleNamespace(
        status="LISTEN",
        laddr=SimpleNamespace(port=9222),
        pid=789,
    )
    fake_psutil(
        monkeypatch,
        connections=[connection],
        executable=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )

    assert not bridge_identity.loopback_listener_is_brave(9222)


def test_listener_lookup_fails_closed_when_process_table_is_unavailable(monkeypatch):
    fake_psutil(monkeypatch, error=OSError("process table unavailable"))

    assert not bridge_identity.loopback_listener_is_brave(9222)
