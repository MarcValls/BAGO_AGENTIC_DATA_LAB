"""Compatibility of the shared tool loop with and without a web grant."""
import asyncio
from types import SimpleNamespace

import pytest

from src.api import server


@pytest.mark.parametrize('messages', [[], [{'role': 'user', 'content': 'Read the project'}]])
def test_no_web_grant_accepts_empty_context_and_preserves_user_message(monkeypatch, messages):
    observed = []
    original_user = [dict(message) for message in messages]
    monkeypatch.setattr(server.ollama, 'chat_turn', lambda model, turns, **kwargs: observed.append(list(turns)) or {'content': 'Done'})
    answer, sources, events, navigation = asyncio.run(server._chat_with_workspace_read('fixture', messages, []))
    assert answer == 'Done' and sources == [] and events == [] and navigation is None
    assert observed[0][0]['role'] == 'system'
    assert 'No public web read permission' in observed[0][0]['content']
    assert observed[0][1:] == original_user


@pytest.mark.parametrize('messages', [[], [{'role': 'user', 'content': 'Read the public page'}]])
def test_web_grant_instructions_use_system_context_without_rewriting_user(monkeypatch, messages):
    observed = []
    monkeypatch.setattr(server, '_web_reader', lambda permit: object())
    monkeypatch.setattr(server.ollama, 'chat_turn', lambda model, turns, **kwargs: observed.append(list(turns)) or {'content': 'Done'})
    permit = SimpleNamespace(origins=('https://example.com',))
    original_user = [dict(message) for message in messages]
    answer, _, _, _ = asyncio.run(server._chat_with_workspace_read('fixture', messages, [], web_permit=permit))
    assert answer == 'Done'
    assert observed[0][0]['role'] == 'system'
    assert 'https://example.com' in observed[0][0]['content']
    assert 'untrusted' in observed[0][0]['content'].lower()
    if original_user:
        assert observed[0][1:] == original_user
