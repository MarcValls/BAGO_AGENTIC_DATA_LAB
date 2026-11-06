import subprocess
import json
import os
import socket

import pytest

from src.voice_bridge import VoiceBridge, VoiceBridgeError


def test_invalid_voice_configuration_does_not_abort_bridge_construction(tmp_path):
    config = tmp_path / 'integration.json'
    config.write_text('{invalid', encoding='utf-8')

    bridge = VoiceBridge(config_path=config, token_path=tmp_path / 'receiver.token')
    try:
        with pytest.raises(VoiceBridgeError, match='voice_config_invalid'):
            bridge.status()
    finally:
        bridge.close()


def test_unowned_listener_is_not_adopted_or_given_the_voice_token(tmp_path, monkeypatch):
    root = tmp_path / 'voice'
    python = root / '.venv' / 'Scripts' / 'python.exe'
    python.parent.mkdir(parents=True)
    python.touch()
    script = root / 'voz_local.py'
    script.touch()
    config = tmp_path / 'integration.json'
    config.write_text(json.dumps({'schema': 'bago.voice.integration.v1', 'project_root': str(root), 'port': 18766}), encoding='utf-8')
    token_path = tmp_path / 'receiver.token'
    token_path.write_text('sensitive-test-token-value-0123456789', encoding='utf-8')
    bridge = VoiceBridge(config_path=config, token_path=token_path)
    monkeypatch.setattr(bridge, '_port_has_listener', lambda: True)
    monkeypatch.setattr('src.voice_bridge.subprocess.Popen', lambda *args, **kwargs: pytest.fail('must not start or adopt an unowned listener'))
    try:
        with pytest.raises(VoiceBridgeError, match='voice_port_in_use'):
            bridge._ensure_ready()
        assert bridge._process is None
    finally:
        bridge.close()


def test_health_label_from_a_different_process_is_not_trusted(tmp_path, monkeypatch):
    bridge = VoiceBridge(config_path=tmp_path / 'missing.json', token_path=tmp_path / 'receiver.token')

    class RunningProcess:
        pid = 41001

        @staticmethod
        def poll():
            return None

    bridge._process = RunningProcess()
    monkeypatch.setattr(bridge, '_listener_process_ids', lambda port: {41002})
    monkeypatch.setattr(bridge, '_owned_http', lambda *args, **kwargs: pytest.fail('health without a job must not be queried'))
    try:
        assert bridge._health() is None
    finally:
        bridge._process = None
        bridge.close()


def test_listener_table_reports_the_current_process_on_windows():
    if os.name != 'nt':
        pytest.skip('Windows GetExtendedTcpTable contract')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        owners = VoiceBridge._listener_process_ids(port)
        assert owners is not None
        assert os.getpid() in owners


def test_unpaired_surrogate_is_rejected_before_voice_runtime_or_transport(tmp_path, monkeypatch):
    bridge = VoiceBridge(config_path=tmp_path / 'missing.json', token_path=tmp_path / 'receiver.token')
    monkeypatch.setattr(bridge, '_request', lambda *args: pytest.fail('invalid text must not reach the bridge'))
    try:
        with pytest.raises(VoiceBridgeError, match='voice_request_invalid'):
            bridge.speak('\ud800')
    finally:
        bridge.close()


def test_timeout_retains_owned_child_and_retries_do_not_spawn_another(tmp_path, monkeypatch):
    root = tmp_path / 'voice'
    python = root / '.venv' / 'Scripts' / 'python.exe'
    python.parent.mkdir(parents=True)
    python.touch()
    (root / 'voz_local.py').touch()
    config = tmp_path / 'integration.json'
    config.write_text(json.dumps({'schema':'bago.voice.integration.v1','project_root':str(root),'port':18766}), encoding='utf8')
    bridge = VoiceBridge(config_path=config, token_path=tmp_path / 'token')
    class Child:
        pid = 5678
        def __init__(self): self.alive = True; self.terminate_calls = 0
        def poll(self): return None if self.alive else 0
        def terminate(self): self.terminate_calls += 1; self.alive = False
        def wait(self, timeout): return 0
    child = Child()
    launched = []
    def start(*args, **kwargs): launched.append(args); return child
    class Job:
        def launch(self, *args, **kwargs): return start(*args, **kwargs)
        def terminate(self): child.terminate(); return True
        def is_empty(self): return True
        def close(self): return True
    monkeypatch.setattr('src.voice_bridge.OwnedVoiceJob', Job)
    monkeypatch.setattr(bridge, '_health', lambda: None)
    monkeypatch.setattr(bridge, '_port_has_listener', lambda: False)
    ticks = iter([0, 13, 20, 33])
    monkeypatch.setattr('src.voice_bridge.time.monotonic', lambda: next(ticks))
    try:
        for _ in range(2):
            with pytest.raises(VoiceBridgeError, match='voice_start_timeout'):
                bridge._ensure_ready()
            assert bridge._process is child
            assert bridge.status()['state'] == 'STARTING'
        assert len(launched) == 1
    finally:
        bridge.close()
    assert child.terminate_calls == 1
    assert bridge._process is None


def test_close_retains_reference_when_owned_child_does_not_stop(tmp_path):
    import subprocess
    bridge = VoiceBridge(config_path=tmp_path / 'missing.json', token_path=tmp_path / 'token')
    class StuckChild:
        def poll(self): return None
        def terminate(self): raise OSError('cannot terminate')
        def kill(self): raise OSError('cannot kill')
    child = StuckChild()
    bridge._process = child
    bridge.close()
    assert bridge._process is child
    # No real subprocess was created; remove the stub before the atexit hook.
    bridge._process = None

@pytest.mark.parametrize('termination_ok,exited,empty,close_ok', [(False,True,True,True),(True,False,True,True),(True,True,False,True),(True,True,True,False)])
def test_cleanup_failures_preserve_ownership(tmp_path, termination_ok, exited, empty, close_ok):
    bridge = VoiceBridge(config_path=tmp_path/'missing', token_path=tmp_path/'token')
    class Job:
        def terminate(self): return termination_ok
        def is_empty(self): return empty
        def close(self): return close_ok
    class Process:
        def wait(self, timeout):
            if not exited: raise subprocess.TimeoutExpired('synthetic', timeout)
        def poll(self): return 0 if exited else None
    job, process = Job(), Process()
    bridge._job, bridge._process = job, process
    assert bridge.close() is False
    assert bridge._job is job and bridge._process is process
    bridge._job = None; bridge._process = None

def test_failed_launch_retains_job_if_cleanup_fails(tmp_path, monkeypatch):
    bridge = VoiceBridge(config_path=tmp_path/'missing', token_path=tmp_path/'token')
    bridge._root = tmp_path
    bridge._python = tmp_path/'python.exe'; bridge._python.touch()
    bridge._script = tmp_path/'voz_local.py'; bridge._script.touch()
    class Job:
        def launch(self, *args, **kwargs): raise OSError('synthetic')
        def terminate(self): return False
        def is_empty(self): pytest.fail('must retain failed termination')
        def close(self): pytest.fail('must retain handle')
    job = Job()
    monkeypatch.setattr('src.voice_bridge.OwnedVoiceJob', lambda: job)
    monkeypatch.setattr(bridge, '_port_has_listener', lambda: False)
    with pytest.raises(VoiceBridgeError, match='voice_cleanup_failed'):
        bridge._ensure_ready()
    assert bridge._job is job
    bridge._job = None
