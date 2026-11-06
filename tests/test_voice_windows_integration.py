import json
import os
from pathlib import Path
import socket
import sys
import threading

import pytest

from src.voice_bridge import VoiceBridge, VoiceBridgeError

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object integration')


def test_real_bridge_owned_receiver_and_foreign_socket(tmp_path):
    # Synthetic server: receives no real token, text, or microphone data.
    script = tmp_path / 'voz_local.py'
    script.write_text('''import http.server,json,sys\nfrom pathlib import Path\na=sys.argv; port=int(a[a.index("--puerto")+1]); Path(a[a.index("--token-file")+1]).write_text("x"*40)\nclass H(http.server.BaseHTTPRequestHandler):\n def log_message(self,*a): pass\n def do_GET(self):\n  self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"app":"Voz Local Receptor"}).encode())\n def do_POST(self):\n  data=self.rfile.read(int(self.headers.get("Content-Length",0))); self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"received":len(data)}).encode())\nhttp.server.HTTPServer(("127.0.0.1",port),H).serve_forever()\n''', encoding='utf8')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    bridge = VoiceBridge(config_path=tmp_path/'missing.json', token_path=tmp_path/'token')
    bridge._root, bridge._python, bridge._script, bridge._port = tmp_path, Path(os.environ.get("BAGO_VOICE_TEST_PYTHON", sys.executable)), script, port
    try:
        result = bridge.speak('synthetic')
        assert result['received'] > 0
        assert bridge.status()['state'] == 'READY'
    finally:
        bridge.close()
    assert bridge._job is None
    foreign = socket.socket(); foreign.bind(('127.0.0.1', 0)); foreign.listen(1)
    foreign.settimeout(5); bridge._port = foreign.getsockname()[1]
    received = []
    def accept():
        conn, _ = foreign.accept()
        with conn:
            conn.settimeout(3); received.append(conn.recv(1024))
    thread = threading.Thread(target=accept); thread.start()
    job = __import__('src.voice_windows_job', fromlist=['OwnedVoiceJob']).OwnedVoiceJob()
    bridge._job = job
    try:
        with pytest.raises(VoiceBridgeError, match='voice_peer_unverified'):
            bridge._owned_http('POST','/speak', b'synthetic', {'X-Voz-Token':'synthetic'})
        thread.join(timeout=5)
        assert received == [b'']
    finally:
        job.terminate(); job.close(); bridge._job = None; foreign.close(); thread.join(timeout=5)
