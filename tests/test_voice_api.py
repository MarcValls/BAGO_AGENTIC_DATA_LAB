from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.voice_routes import create_voice_router


class StubVoice:
    def __init__(self):
        self.calls = []

    def status(self):
        return {'state': 'ready'}

    def speak(self, text, voice, speed):
        self.calls.append(('speak', text, voice, speed))
        return {'id': 'fixture'}

    def transcribe(self, audio, content_type):
        self.calls.append(('transcribe', audio, content_type))
        return {'text': 'fixture'}

    def request_status(self, request_id):
        return {'id': request_id}


def client():
    bridge = StubVoice()
    app = FastAPI()
    app.include_router(create_voice_router(bridge))
    return TestClient(app, base_url='http://127.0.0.1:8080'), bridge


def test_voice_router_accepts_same_origin_and_uses_exact_audio_bytes():
    http, bridge = client()
    response = http.post('/api/voice/transcribe', content=b'fixture-audio', headers={'origin': 'http://127.0.0.1:8080', 'content-type': 'audio/webm'})
    assert response.status_code == 200
    assert response.json() == {'text': 'fixture'}
    assert bridge.calls == [('transcribe', b'fixture-audio', 'audio/webm')]


def test_voice_router_rejects_cross_origin_before_speech():
    http, bridge = client()
    response = http.post('/api/voice/speak', json={'text': 'hello'}, headers={'origin': 'http://foreign.example'})
    assert response.status_code == 403
    assert bridge.calls == []


def test_voice_router_rejects_unknown_audio_format():
    http, bridge = client()
    response = http.post('/api/voice/transcribe', content=b'fixture', headers={'content-type': 'text/plain'})
    assert response.status_code == 415
    assert bridge.calls == []


def test_transcription_does_not_block_concurrent_status_request():
    import asyncio
    import threading
    import httpx

    started = threading.Event()
    release = threading.Event()
    class SlowVoice(StubVoice):
        def transcribe(self, audio, content_type):
            started.set()
            release.wait(3)
            return {'text': 'fixture'}

    async def exercise():
        bridge = SlowVoice()
        app = FastAPI()
        app.include_router(create_voice_router(bridge))
        # This ensures a broken event loop eventually exits rather than hanging the suite.
        timer = threading.Timer(3, release.set)
        timer.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8080') as http:
                task = asyncio.create_task(http.post('/api/voice/transcribe', content=b'fixture', headers={'content-type': 'audio/webm'}))
                assert await asyncio.to_thread(started.wait, 1)
                status = await asyncio.wait_for(http.get('/api/voice/status'), timeout=1)
                assert status.status_code == 200
                assert not release.is_set(), 'status waited for the blocked transcription'
                release.set()
                assert (await task).status_code == 200
        finally:
            release.set()
            timer.cancel()
    asyncio.run(exercise())


def test_voice_router_rejects_matching_arbitrary_host_and_origin():
    http, bridge = client()
    response = http.post('/api/voice/speak', json={'text': 'fixture'}, headers={'host': 'foreign.example', 'origin': 'http://foreign.example'})
    assert response.status_code == 403
    assert http.post('/api/voice/speak', json={'text': 'fixture'}, headers={'host': 'foreign.example'}).status_code == 403
    assert bridge.calls == []


def test_voice_router_accepts_loopback_hosts_and_matching_origins():
    http, bridge = client()
    for host in ('127.0.0.1:8080', 'localhost:8080', '[::1]:8080'):
        response = http.post('/api/voice/speak', json={'text': 'fixture'}, headers={'host': host, 'origin': 'http://' + host})
        assert response.status_code == 200, host
    assert len(bridge.calls) == 3


def test_voice_router_accepts_native_loopback_client_without_origin():
    http, bridge = client()
    assert http.get('/api/voice/status').status_code == 200
    assert http.post('/api/voice/speak', json={'text': 'fixture'}).status_code == 200
    assert len(bridge.calls) == 1


def test_voice_router_rejects_different_or_malformed_origin():
    http, bridge = client()
    for origin in ('http://localhost:8080', 'null', 'http://127.0.0.1:8080/path'):
        response = http.post('/api/voice/speak', json={'text': 'fixture'}, headers={'origin': origin})
        assert response.status_code == 403, origin
    assert bridge.calls == []
