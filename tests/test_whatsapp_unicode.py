"""Unicode ownership boundary. Synthetic fixtures; one CIM read of an owned test process.

No browser is opened, contacted, closed or controlled, and no message is sent.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import src.whatsapp.session as module


def windows_probe(monkeypatch, command=None, error=None):
    def run(argv, **kwargs):
        assert kwargs.get("encoding") == "utf-8"
        assert kwargs.get("errors") == "strict"
        assert "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false);" in argv[-1]
        if error:
            raise error
        return SimpleNamespace(stdout=command.encode("utf-8").decode(kwargs["encoding"], errors=kwargs["errors"]), returncode=0)
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(module.subprocess, "run", Mock(side_effect=run))


def test_process_arguments_decodes_unicode_without_loss(monkeypatch):
    command = '"C:/Program Files/Brave/brave.exe" --user-data-dir="C:/empresa-ñ-º-财/perfil" --remote-debugging-port=9333'
    windows_probe(monkeypatch, command + "\r\n")
    assert module.process_arguments(17) == command
    assert "ProcessId = 17" in module.subprocess.run.call_args.args[0][-1]


@pytest.mark.parametrize("mutation", [None, "profile", "port", "executable"])
def test_unicode_owner_remains_exact_and_conservative(tmp_path, monkeypatch, mutation):
    session = module.WhatsAppSession(tmp_path / "empresa-ñ-º-财")
    session.root.mkdir()
    owner = {"pid": 17, "port": 9333, "profile": str(session.profile)}
    (session.root / "browser.json").write_text(json.dumps(owner), encoding="utf-8")
    profile = str(session.profile) + ("-other" if mutation == "profile" else "")
    port = 93330 if mutation == "port" else 9333
    executable = "evil.exe" if mutation == "executable" else "brave.exe"
    windows_probe(monkeypatch, f'"C:/Program Files/Brave/{executable}" --user-data-dir="{profile}" --remote-debugging-port={port}')
    assert session._owner() == (owner if mutation is None else None)


@pytest.mark.parametrize("error", [UnicodeDecodeError("utf-8", b"\xa7", 0, 1, "invalid byte"), subprocess.TimeoutExpired("powershell", 5), OSError("process inaccessible")])
def test_probe_failure_still_denies_ownership(tmp_path, monkeypatch, error):
    session = module.WhatsAppSession(tmp_path)
    (tmp_path / "browser.json").write_text(json.dumps({"pid": 17, "port": 9333, "profile": str(session.profile)}))
    windows_probe(monkeypatch, error=error)
    assert session._owner() is None


@pytest.mark.skipif(os.name != "nt", reason="Read-only Windows CIM subprocess regression")
def test_real_cim_roundtrip_on_own_unicode_fixture_process():
    marker = "empresa-ñ-º-财"
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)", marker],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        command = module.process_arguments(child.pid)
        assert marker in command
    finally:
        child.communicate(b"x", timeout=15)
    assert child.returncode == 0
