from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "brave-browser-mcp"))
import identity  # noqa: E402

BRAVE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"


@pytest.fixture
def server_module(monkeypatch):
    # CI installs the project dependencies, while Playwright belongs to this
    # optional bridge. These tests simulate its boundary and open no browser.
    if importlib.util.find_spec("playwright") is None:
        parent = ModuleType("playwright")
        parent.__path__ = []
        api = ModuleType("playwright.async_api")
        api.Browser = api.Page = api.Playwright = object
        api.async_playwright = lambda: None
        monkeypatch.setitem(sys.modules, "playwright", parent)
        monkeypatch.setitem(sys.modules, "playwright.async_api", api)
    spec = importlib.util.spec_from_file_location(
        "bago_brave_test_server", ROOT / "tools" / "brave-browser-mcp" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_psutil(monkeypatch, connections=(), executables=None, error=None):
    class AccessDenied(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    def net_connections(kind):
        if error:
            raise error
        return connections

    def process(pid):
        return SimpleNamespace(exe=lambda: (executables or {})[pid])

    monkeypatch.setattr(identity, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "psutil", SimpleNamespace(
        CONN_LISTEN="LISTEN", AccessDenied=AccessDenied,
        NoSuchProcess=NoSuchProcess, net_connections=net_connections, Process=process,
    ))


def listener(ip, port=9222, pid=1):
    return SimpleNamespace(status="LISTEN", laddr=SimpleNamespace(ip=ip, port=port), pid=pid)


def test_listener_matches_exact_loopback_and_configured_executable(monkeypatch):
    fake_psutil(monkeypatch, [listener("127.0.0.1")], {1: BRAVE})
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "MATCH"


def test_other_address_with_same_port_cannot_identify_loopback(monkeypatch):
    fake_psutil(monkeypatch, [listener("192.168.1.20")], {1: BRAVE})
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "ABSENT"


@pytest.mark.parametrize("address", ["0.0.0.0", "::"])
def test_wildcard_listener_blocks_attach_and_launch(monkeypatch, address):
    fake_psutil(monkeypatch, [listener(address)], {1: BRAVE})
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "MISMATCH"


def test_same_executable_name_at_other_path_is_rejected(monkeypatch):
    fake_psutil(monkeypatch, [listener("127.0.0.1")], {1: r"C:\Other\brave.exe"})
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "MISMATCH"


def test_ipv6_loopback_is_matched_to_its_own_listener(monkeypatch):
    fake_psutil(monkeypatch, [listener("::1")], {1: BRAVE})
    assert identity.listener_state("::1", 9222, BRAVE) == "MATCH"


def test_listener_without_pid_is_unknown(monkeypatch):
    fake_psutil(monkeypatch, [listener("127.0.0.1", pid=None)])
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "UNKNOWN"


def test_inaccessible_process_table_is_unknown(monkeypatch):
    fake_psutil(monkeypatch, error=OSError("access denied"))
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "UNKNOWN"


def test_multiple_matching_listeners_are_unknown(monkeypatch):
    fake_psutil(monkeypatch, [listener("127.0.0.1", pid=1), listener("127.0.0.1", pid=2)])
    assert identity.listener_state("127.0.0.1", 9222, BRAVE) == "UNKNOWN"


def setup_session(server, monkeypatch, states):
    monkeypatch.setattr(server, "DEFAULT_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(server.BraveSession, "_brave_executable", staticmethod(lambda: BRAVE))
    states = iter(states)
    monkeypatch.setattr(server, "listener_state", lambda *args: next(states))
    session = server.BraveSession()
    session._launch_brave = Mock()
    browser = SimpleNamespace(close=AsyncMock())
    connect = AsyncMock(return_value=browser)
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
    monkeypatch.setattr(server, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=playwright)))
    return session, browser, connect


@pytest.mark.parametrize("state", ["MISMATCH", "UNKNOWN"])
def test_unverified_listener_never_launches_or_connects(server_module, monkeypatch, state):
    session, _, connect = setup_session(server_module, monkeypatch, [state])
    with pytest.raises(RuntimeError, match="Cannot verify Brave listener"):
        asyncio.run(session.ensure_connected())
    session._launch_brave.assert_not_called()
    connect.assert_not_awaited()


def test_verified_listener_is_checked_again_after_connection(server_module, monkeypatch):
    session, browser, connect = setup_session(server_module, monkeypatch, ["MATCH", "MATCH", "MATCH"])
    assert asyncio.run(session.ensure_connected()) is browser
    connect.assert_awaited_once_with("http://127.0.0.1:9222", timeout=1500)
    session._launch_brave.assert_not_called()


def test_changed_listener_is_not_returned(server_module, monkeypatch):
    session, browser, _ = setup_session(server_module, monkeypatch, ["MATCH", "MATCH", "MISMATCH"])
    with pytest.raises(RuntimeError, match="changed during connection"):
        asyncio.run(session.ensure_connected())
    browser.close.assert_awaited_once()
    assert session.browser is None


def test_absent_listener_launches_once_then_verifies(server_module, monkeypatch):
    session, browser, _ = setup_session(server_module, monkeypatch, ["ABSENT", "MATCH", "MATCH"])
    assert asyncio.run(session.ensure_connected()) is browser
    session._launch_brave.assert_called_once_with("127.0.0.1", 9222, BRAVE)


def test_existing_connection_is_not_reused_after_listener_changes(server_module, monkeypatch):
    session, browser, connect = setup_session(server_module, monkeypatch, ["MISMATCH"])
    browser.is_connected = Mock(return_value=True)
    session.browser = browser
    session.connected_endpoint = "http://127.0.0.1:9222"
    with pytest.raises(RuntimeError, match="Cannot verify existing Brave listener"):
        asyncio.run(session.ensure_connected())
    browser.close.assert_awaited_once()
    connect.assert_not_awaited()


def test_localhost_reuses_an_existing_ipv6_listener(server_module, monkeypatch):
    session, browser, connect = setup_session(server_module, monkeypatch, [])
    monkeypatch.setattr(server_module, "DEFAULT_CDP_URL", "http://localhost:9222")
    monkeypatch.setattr(server_module, "listener_state", lambda address, *_: "MATCH" if address == "::1" else "ABSENT")
    assert asyncio.run(session.ensure_connected()) is browser
    connect.assert_awaited_once_with("http://[::1]:9222", timeout=1500)
    session._launch_brave.assert_not_called()


def test_ambiguous_localhost_listeners_do_not_start_a_browser(server_module, monkeypatch):
    session, _, connect = setup_session(server_module, monkeypatch, [])
    monkeypatch.setattr(server_module, "DEFAULT_CDP_URL", "http://localhost:9222")
    monkeypatch.setattr(server_module, "listener_state", lambda *args: "MATCH")
    with pytest.raises(RuntimeError, match="ambiguous"):
        asyncio.run(session.ensure_connected())
    session._launch_brave.assert_not_called()
    connect.assert_not_awaited()


def test_other_ipv6_listener_prevents_duplicate_localhost_launch(server_module, monkeypatch):
    session, _, connect = setup_session(server_module, monkeypatch, [])
    monkeypatch.setattr(server_module, "DEFAULT_CDP_URL", "http://localhost:9222")
    monkeypatch.setattr(server_module, "listener_state", lambda address, *_: "MISMATCH" if address == "::1" else "ABSENT")
    with pytest.raises(RuntimeError, match="Cannot safely resolve localhost"):
        asyncio.run(session.ensure_connected())
    session._launch_brave.assert_not_called()
    connect.assert_not_awaited()


def test_connection_is_not_reused_for_a_different_resolved_endpoint(server_module, monkeypatch):
    session, browser, connect = setup_session(server_module, monkeypatch, ["MATCH"])
    browser.is_connected = Mock(return_value=True)
    session.browser = browser
    session.connected_endpoint = "http://[::1]:9222"
    with pytest.raises(RuntimeError, match="Cannot verify existing Brave listener"):
        asyncio.run(session.ensure_connected())
    browser.close.assert_awaited_once()
    connect.assert_not_awaited()


def test_port_zero_is_rejected_without_connecting(server_module, monkeypatch):
    session, _, connect = setup_session(server_module, monkeypatch, [])
    monkeypatch.setattr(server_module, "DEFAULT_CDP_URL", "http://127.0.0.1:0")
    with pytest.raises(RuntimeError, match="port must be"):
        asyncio.run(session.ensure_connected())
    session._launch_brave.assert_not_called()
    connect.assert_not_awaited()
