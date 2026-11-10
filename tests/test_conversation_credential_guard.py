import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api import server
from src.conversations.credential_guard import contains_credential_tree, redact_credential_tree
from src.conversations.library import ConversationStore


def test_user_credential_rejected_and_assistant_data_redacted(tmp_path):
    marker = 'synthetic-only-secret-value'
    db = tmp_path / 'conversations.sqlite'
    store = ConversationStore(db)
    conversation = store.create('assistant', 'agent')
    with pytest.raises(ValueError):
        store.append_message(conversation['id'], 0, 'user', 'password: ' + marker)
    assert store.get(conversation['id'])['revision'] == 0
    store.append_message(conversation['id'], 0, 'assistant', 'result', {'oauth': {'refresh_token': marker}})
    assert marker not in str(store.get(conversation['id']))
    assert marker.encode() not in db.read_bytes()


@pytest.mark.parametrize('key', ['api_key', 'Authorization'])
def test_nested_sensitive_values_do_not_persist(tmp_path, key):
    marker = 'synthetic-nonpattern-credential'
    data = {key: {'value': marker, 'inner': [None, {'credential_value': marker}]}}
    assert contains_credential_tree(data)
    assert marker not in str(redact_credential_tree(data))
    text = json.dumps(data)
    assert contains_credential_tree(text)
    assert marker not in redact_credential_tree(text)
    store = ConversationStore(tmp_path / 'nested.sqlite')
    conversation = store.create('assistant', 'agent')
    store.append_message(conversation['id'], 0, 'assistant', 'result', data)
    assert marker not in str(store.get(conversation['id']))
    assert marker.encode() not in (tmp_path / 'nested.sqlite').read_bytes()


def test_nested_nonsensitive_data_preserved():
    for value in ({'metadata': {'value': 'ordinary'}}, {'api_key': {'value': '', 'enabled': False, 'count': 0, 'none': None}}, {'Authorization': 'allow'}):
        assert not contains_credential_tree(value)
        assert redact_credential_tree(value) == value


def test_authorization_metadata_preserved_when_nested_credentials_redacted():
    value = {'authorization': {'kind': 'channel_task', 'grant_id': 'grant-123',
             'payload': {'text': 'hello'}, 'value': 'synthetic-nonpattern-credential',
             'nested': {'api_key': 'synthetic-other-credential'}}}
    for original in (value, json.dumps(value)):
        assert contains_credential_tree(original)
        result = redact_credential_tree(original)
        if isinstance(result, str):
            result = json.loads(result)
        auth = result['authorization']
        assert auth['kind'] == 'channel_task'
        assert auth['grant_id'] == 'grant-123'
        assert auth['payload']['text'] == 'hello'
        assert auth['value'] == '[REDACTED]'
        assert auth['nested']['api_key'] == '[REDACTED]'


@pytest.mark.parametrize('item', [
    {'authorization': ['Bearer synthetic-unpattern-secret']},
    {'authorization': {'header': 'Bearer synthetic-unpattern-secret'}},
])
def test_authorization_header_and_list_are_detected_and_redacted(item):
    for value in (item, json.dumps(item)):
        assert contains_credential_tree(value)
        assert 'synthetic-unpattern-secret' not in str(redact_credential_tree(value))


def test_deep_authorization_has_linear_visits(monkeypatch):
    from src.conversations import credential_guard as guard
    depth = 48
    raw = '{"authorization":' * depth + '{"kind":"channel_task","header":"Bearer synthetic-nonpattern"}' + '}' * depth
    calls = 0
    original = guard._authorization_visit

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(guard, '_authorization_visit', counted)
    result = guard.redact_credential_tree(raw)
    assert 'synthetic-nonpattern' not in result
    assert 'channel_task' in result
    assert calls <= depth * 3 + 10


def test_deep_sensitive_json_visits_each_node_once_and_preserves_pairs(monkeypatch):
    from src.conversations import credential_guard as guard

    depth = 48
    raw = '{"api_key":' + '{"value":' * depth + '{"value":"synthetic-nonpattern-credential","value":null}' + '}' * depth + '}'
    calls = 0
    original = guard._redact_json_node

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(guard, '_redact_json_node', counted)
    result = guard.redact_credential_tree(raw)
    assert 'synthetic-nonpattern-credential' not in result
    assert '"value": "[REDACTED]", "value": null' in result
    assert calls <= depth + 5


def test_json_duplicate_keys_collisions_and_safe_content():
    raw = '{"password":"synthetic-secret","password":null,"password=one-secret":1,"password=two-secret":2,"[REDACTED]":3}'
    assert contains_credential_tree(raw)
    clean = redact_credential_tree(raw)
    assert 'synthetic-secret' not in clean
    assert sorted(v for v in json.loads(clean).values() if isinstance(v, int)) == [1, 2, 3]
    for text in ('I am the bearer of bad news.', 'bearer responsibility', 'sha256: ' + 'a' * 64, '{"password":""}'):
        assert not contains_credential_tree(text)
        assert redact_credential_tree(text) == text
    assert contains_credential_tree('Authorization: Bearer synthetic')
    assert 'synthetic' not in redact_credential_tree('Authorization: Bearer synthetic')


def test_chat_rejects_before_provider():
    async def run():
        request = SimpleNamespace(message='password: synthetic-early-marker')
        for invoke in (lambda: server.control_chat(request), lambda: server._execute_agent_chat_turn('agent', request, None)):
            with pytest.raises(HTTPException) as error:
                await invoke()
            assert error.value.status_code == 422
            assert error.value.detail['code'] == 'credential_in_chat'
            assert 'synthetic-early-marker' not in str(error.value.detail)
    asyncio.run(run())

def test_provider_tool_call_with_credential_has_no_effect(tmp_path):
    class Filesystem:
        def __init__(self):
            self.calls = []
        def schemas(self, ids):
            return []
        def execute(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise AssertionError('unexpected effect')
    async def run():
        marker = 'synthetic-only-refresh-secret'
        filesystem = Filesystem()
        turn = {'tool_calls': [{'id': 'c1', 'function': {'name': 'filesystem_plan', 'arguments': {
            'operation': 'write', 'target': 'fixture.txt', 'content': 'ok', 'refresh_token': marker}}}]}
        with patch.object(server.provider_runtime, 'chat_turn', return_value=turn):
            answer, _, _, _ = await server._chat_with_workspace_read(
                'synthetic-model', [{'role': 'user', 'content': 'prepare file'}], [],
                provider_id='synthetic-provider', workspace_root=tmp_path, filesystem_service=filesystem)
        assert not filesystem.calls
        assert 'credencial' in answer.lower() and marker not in answer
        assert not list(tmp_path.iterdir())
    asyncio.run(run())


def test_code_references_do_not_reveal_literal_secrets():
    safe = ('password=os.environ.get("PASSWORD")', 'api_key=os.getenv("API_KEY")', 'password=input()')
    for text in safe:
        assert not contains_credential_tree(text)
        assert redact_credential_tree(text) == text
    unsafe = ('password="synthetic-secret"', 'password=os.getenv("PASSWORD", "synthetic-secret")',
              'password=os.getenv("PASSWORD"); api_key="synthetic-secret"')
    for text in unsafe:
        assert contains_credential_tree(text)
        assert 'synthetic-secret' not in redact_credential_tree(text)


def test_comment_does_not_bypass_credential_guard():
    text = 'password = os.getenv("PASSWORD") # password=synthetic-comment-secret'
    assert contains_credential_tree(text)
    assert 'synthetic-comment-secret' not in redact_credential_tree(text)
    safe = 'password = os.getenv("PASSWORD#SCOPE")'
    assert not contains_credential_tree(safe)
    assert redact_credential_tree(safe) == safe


def test_authorization_header_inside_environment_argument_is_redacted():
    text = 'password = os.getenv("Authorization: Bearer synthetic-header-secret")'
    assert contains_credential_tree(text)
    assert 'synthetic-header-secret' not in redact_credential_tree(text)


def test_code_references_and_concatenated_literals():
    safe = ('password=input("Password: ")', 'password=os.environ["PASSWORD"]',
            'import os\napi_key=os.getenv("API_KEY")')
    for text in safe:
        assert not contains_credential_tree(text)
        assert redact_credential_tree(text) == text
    for text in ('password="synthetic-" "secret"', 'password="synthetic-" + "secret"',
                 'password=input("Password: ") # password=synthetic-secret'):
        assert contains_credential_tree(text)
        assert 'secret' not in redact_credential_tree(text)


def test_concatenated_recognizable_credentials_in_any_assignment():
    for text in ('x="sk-" "synthetic123456789"',
                 'x=os.getenv("Authorization: " "Bearer synthetic-secret")',
                 'x="sk-" + "synthetic123456789"'):
        assert contains_credential_tree(text)
        assert 'synthetic' not in redact_credential_tree(text)
    for text in ('x="hello" " world"', 'x=os.getenv("API_KEY")'):
        assert not contains_credential_tree(text)
        assert redact_credential_tree(text) == text


def test_long_literal_concatenation_without_quadratic_ast_walk():
    safe = 'x=' + '+'.join(['"hello"'] * 600)
    dangerous = 'x=' + '+'.join(['"hello"'] * 600 + ['"Authorization: "', '"Bearer synthetic-secret"'])
    assert not contains_credential_tree(safe)
    assert redact_credential_tree(safe) == safe
    assert contains_credential_tree(dangerous)
    assert 'synthetic-secret' not in redact_credential_tree(dangerous)

@pytest.mark.parametrize('text', [
    'x = "sk-" + """synthetic\\x3123456789012345\\',
    'x = "sk-" + """synthetic\\\n123456789012345\\',
    'x = ("sk-" + # nota\n "synthetic123456789012345',
    'x = "sk-" u"synthetic123456789012345',
    'x = "sk-" r"synthetic123456789012345',
    'x = "sk-" + U"synthetic123456789012345',
])
def test_truncated_literal_credentials_are_redacted(text):
    assert contains_credential_tree(text)
    assert 'synthetic' not in redact_credential_tree(text)


@pytest.mark.parametrize('text', [
    'x = "sk-" + r"""synthetic\\x3123456789012345\\',
    'x = "sk-" + """synthetic\n123456789012345',
    'x = "sk-" + """synthetic 123456789012345',
    'api_key = os.getenv("API_KEY") # comentario',
    'x = "sk-" + "abc" # synthetic123456789012345',
    'x = "sk-" u "synthetic123456789012345',
    'x = "hello" u"unfinished',
])
def test_truncated_literal_whitespace_raw_and_comments_are_preserved(text):
    assert not contains_credential_tree(text)
    assert redact_credential_tree(text) == text
