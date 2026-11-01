"""Real durable conversation/admission/service; controlled transport, no WhatsApp network."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from src.communications import CommunicationError, CommunicationService
from src.communications.chat_admission import ChatSendAdmission
from src.communications.service import schedule_value
from src.conversations import ConversationStore
from src.conversations.library import reset_project_scope, set_project_scope


@pytest.fixture
def env(tmp_path, monkeypatch):
    from src.api import server
    project = {'project_id': 'chat-wa', 'root': str(tmp_path), 'binding': 'private-fixture-binding',
        'read_directories': [], 'write_directories': []}
    calls = []
    class Session:
        def authorization_identity(self): return '1' * 64
        def status(self): return {'state': 'connected'}
        def send(self, phone, text, attachments, operation_id):
            calls.append((phone, text, operation_id))
            return {'status': 'sent', 'operation_id': operation_id, 'observed_at': '2026-11-01T12:00:00Z'}
    store = ConversationStore(tmp_path / 'c.sqlite')
    service = CommunicationService(tmp_path / 's', Session(), lambda: tmp_path, project_snapshot=lambda: project)
    admission = ChatSendAdmission(service.root, store, set_project_scope, reset_project_scope, service.contacts)
    service.task_authorizer = admission.authorize
    contact = service.create_contact('Ana Fixture', '+34600000001')
    status = service.whatsapp_authorization()
    grant = service.set_whatsapp_authorization(enabled=True, expected_project_id=project['project_id'],
        expected_binding=project['binding'], expected_session_identity=status['session_identity'],
        expected_authorization_revision=status['revision'])
    token = set_project_scope(project['project_id'])
    conv = store.create('assistant', 'app-assistant')
    monkeypatch.setattr(server, 'CONVERSATIONS', store)
    monkeypatch.setattr(server, '_communication_service', lambda: service)
    monkeypatch.setattr(server, '_current_project_permissions', lambda: SimpleNamespace(snapshot=lambda: project))
    monkeypatch.setattr(server, '_project_read_context', lambda root: None)
    monkeypatch.setattr(server, 'current_workspace_root', lambda: tmp_path)
    monkeypatch.setattr(server, '_record_agent_chat_trace', lambda **kwargs: {'trace_id': 'controlled'})
    monkeypatch.setattr(server.provider_runtime, 'active_selection', lambda: {'provider_id': 'codex', 'model_id': 'fixture'})
    fields = {'contact_id': contact['id'], 'text': 'Hola, prueba privada.'}
    monkeypatch.setattr(server.provider_runtime, 'chat_turn', lambda *a, **k: {'tool_calls': [
        {'function': {'name': 'resolve_control_request', 'arguments': {'decision': 'communication_draft',
            'communication': dict(fields)}}}]})
    try:
        yield SimpleNamespace(server=server, service=service, admission=admission, contact=contact,
            calls=calls, project=project, store=store, conv=conv, grant=grant, fields=fields)
    finally:
        reset_project_scope(token)


def send(e, message):
    return asyncio.run(e.server.control_chat(e.server.ControlChatRequest(
        message=message, conversation_id=e.conv['id'], revision=e.store.get(e.conv['id'])['revision'])))


def test_real_control_chat_single_channel_consent_dispatches_new_human_task(env):
    result = send(env, 'Envía por WhatsApp a Ana Fixture: Hola, prueba privada.')
    draft = result['communication_draft']
    assert draft['state'] == 'sent', result
    assert draft['authorization']['kind'] == 'channel_task'
    assert len(env.calls) == 1
    assert env.store.get(env.conv['id'])['messages'][-1]['references']['communication_draft_id'] == draft['id']
    env.service.tick()
    assert len(env.calls) == 1


def test_real_worker_stop_blocks_immediate_chat_admission(env):
    from src.communications.worker import CommunicationWorker
    worker = CommunicationWorker(env.service)
    async def scenario():
        assert await worker.start()
        worker.stop_event.set()
        try:
            return await env.server.control_chat(env.server.ControlChatRequest(message='Envía por WhatsApp a Ana Fixture: Hola, prueba privada.', conversation_id=env.conv['id'], revision=0))
        finally:
            await worker.stop()
    result = asyncio.run(scenario())
    assert result['operation'] == 'chat'
    assert 'STOP' in result['assistant_message']
    assert env.calls == [] and env.service.runs() == []


def test_real_worker_stop_between_admission_and_transport_blocks_immediate_send(env, monkeypatch):
    from src.communications.worker import CommunicationWorker
    worker = CommunicationWorker(env.service)
    def stopped_probe():
        worker.stop_event.set()
        return {'state': 'connected'}
    monkeypatch.setattr(env.service.session, 'status', stopped_probe)
    async def scenario():
        assert await worker.start()
        try:
            return await env.server.control_chat(env.server.ControlChatRequest(message='Envía por WhatsApp a Ana Fixture: Hola, prueba privada.', conversation_id=env.conv['id'], revision=0))
        finally:
            await worker.stop()
    result = asyncio.run(scenario())
    assert result['communication_draft']['state'] == 'failed'
    assert env.calls == []
    assert 'transport_admitted_at' not in env.service.runs()[0]


def test_constructing_and_starting_nonowner_does_not_replace_active_owner_stop(env):
    from src.communications.worker import CommunicationWorker
    async def scenario():
        owner = CommunicationWorker(env.service)
        assert await owner.start()
        try:
            contender = CommunicationWorker(env.service)
            assert not await contender.start()
            owner.stop_event.set()
            assert env.service._stopping()
        finally:
            await owner.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('message', [
    'No envíes por WhatsApp a Ana Fixture: Hola, prueba privada.',
    'Prepara un borrador por WhatsApp a Ana Fixture: Hola, prueba privada.',
    '"Envía por WhatsApp a Ana Fixture: Hola, prueba privada."',
    'Explica este texto: Envía por WhatsApp a Ana Fixture: Hola, prueba privada.',
    'Envía como borrador por WhatsApp a Ana Fixture: Hola, prueba privada.',
    'Envía por WhatsApp a Otra Persona: Hola, prueba privada.',
    'Envía por WhatsApp a Ana Fixture: El modelo cambió el texto.',
    'Envía por WhatsApp a Ana Fixture cuando te confirme: Hola, prueba privada.',
    'Envía por WhatsApp a Ana Fixture si te doy permiso: Hola, prueba privada.',
    'Envía por WhatsApp a Ana Fixture la semana que viene: Hola, prueba privada.',
    'Envía por WhatsApp a Ana Fixture o a Carlos: Hola, prueba privada.',
    'Envía por WhatsApp a Ana Fixture, pero espera mi confirmación: Hola, prueba privada.',
])
def test_model_fields_cannot_authorize_negated_quoted_draft_or_mismatched_request(env, message):
    result = send(env, message)
    assert env.calls == []
    assert result.get('communication_draft', {}).get('state') in {None, 'draft'}
    assert not env.service.runs()


def prepared(e):
    human = e.store.append_message(e.conv['id'], 0, 'user', 'Envía por WhatsApp a Ana Fixture: Hola, prueba privada.')
    payload = {**e.fields, 'attachments': [], 'schedule': schedule_value({'kind': 'now'}), 'conversation_id': e.conv['id']}
    source = e.admission.prepare(human=human, project=e.project, conversation_id=e.conv['id'],
        payload=payload, session_identity=e.grant['session_identity'])
    return source, payload


def test_background_revalidation_uses_bound_project_and_allows_new_chat_turns(env):
    source, payload = prepared(env)
    env.store.append_message(env.conv['id'], 1, 'assistant', 'Encargo preparado')
    env.store.append_message(env.conv['id'], 2, 'user', 'Otra consulta sin cambiar el encargo')
    token = set_project_scope('some-other-request')
    try:
        assert env.admission.authorize(source, payload, env.project)['authorized'] is True
    finally:
        reset_project_scope(token)


@pytest.mark.parametrize('change', ['deleted', 'archived', 'tampered_receipt', 'payload', 'binding', 'source'])
def test_current_source_and_exact_receipt_rechecked_before_transport(env, change):
    source, payload = prepared(env)
    if change in {'deleted', 'archived'}:
        env.store.set_status(env.conv['id'], 1, change)
    elif change == 'tampered_receipt':
        path = env.admission.root / (source['send_intent_receipt_sha256'] + '.json')
        path.write_text('{}', encoding='utf-8')
    elif change == 'payload': payload['text'] = 'Altered'
    elif change == 'binding': env.project['binding'] = 'other-binding'
    else: source['human_message_sha256'] = '0' * 64
    with pytest.raises((CommunicationError, ValueError)):
        env.admission.authorize(source, payload, env.project)
    assert env.calls == []
