"""Host-owned WhatsApp admission receipts bound to durable human chat tasks.

Channel consent permits the effect; a model's extracted fields never provide
send intent. Ambiguous requests need clarification in the same chat. This
adapter admits explicit direct requests with a named recipient and literal
message after a colon; it does not reinterpret quoted instructions or drafts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .service import CommunicationError, digest, encoded, schedule_value
from src.conversations import ConversationNotFound


def requested_payload(message, payload, contacts):
    """Validate extracted fields against the current human's direct request."""
    match = re.fullmatch(
        r"\s*(?:por favor[, ]*|please\s+)?(?:env[ií]a(?:le|les)?|manda(?:le|les)?|send)\b"
        r"(?P<header>[^:\r\n]{1,500}):\s*(?P<text>[\s\S]+?)\s*", message, re.I)
    if match is None:
        raise CommunicationError("Indica a quién enviar por WhatsApp y el texto después de dos puntos; no se ha enviado.")
    header = match['header']
    # Parse the entire header, not a blacklist of conditional words. Any
    # unconsumed condition, alternative recipient or future time must clarify.
    def matches_recipient(contact):
        name = contact.get('name')
        if not isinstance(name, str) or not name.strip():
            return False
        recipient = re.escape(name)
        route = rf"(?:por\s+whats\s*app\s+a\s+{recipient}|a\s+{recipient}\s+por\s+whats\s*app|whats\s*app\s+to\s+{recipient}|to\s+{recipient}\s+(?:on|via)\s+whats\s*app)"
        return re.fullmatch(rf"\s*(?:(?:ahora|now)\s+)?{route}(?:\s+(?:ahora|now))?\s*", header, re.I) is not None
    named = [c for c in contacts if matches_recipient(c)]
    if len(named) != 1 or named[0]['id'] != payload.get('contact_id'):
        raise CommunicationError("Indica un único contacto existente y no ambiguo.")
    literal = match['text']
    if len(literal) >= 2 and (literal[0], literal[-1]) in {('"', '"'), ("'", "'"), ('«', '»')}:
        literal = literal[1:-1]
    if literal != payload.get('text') or not literal.strip():
        raise CommunicationError("El texto propuesto no coincide con el mensaje solicitado.")
    if payload.get('attachments'):
        raise CommunicationError("Para enviar adjuntos, revisa su alcance y concreta el encargo; no se ha enviado.")
    schedule = schedule_value(payload.get('schedule') or {'kind': 'now'})
    # This bounded literal adapter handles immediate sends. Scheduled and
    # generated-content requests keep their draft and require clarification;
    # they never gain authority merely from extracted model fields.
    if schedule['kind'] != 'now' or re.search(
        r"\b(?:programa|mañana|tomorrow|cada|daily|weekly|después|later|a las|at \d)\b", header, re.I):
        raise CommunicationError("Concreta el calendario del envío en el chat; este adaptador admite envíos inmediatos.")
    return named[0]


class ChatSendAdmission:
    def __init__(self, root, conversations, set_scope, reset_scope, contacts):
        self.root = Path(root) / 'chat-send-intents'
        self.conversations = conversations
        self.set_scope, self.reset_scope = set_scope, reset_scope
        self.contacts = contacts

    def _human(self, project, source):
        token = self.set_scope(project['project_id'])
        try:
            try:
                conversation = self.conversations.get(source['conversation_id'])
            except ConversationNotFound:
                raise CommunicationError("La conversación de origen ya no está disponible.", 403) from None
        finally:
            self.reset_scope(token)
        if (conversation['project_id'] != project['project_id'] or conversation['status'] != 'active'
                or conversation['owner_kind'] != 'assistant' or conversation['owner_id'] != 'app-assistant'
                or conversation['revision'] < source['conversation_revision']):
            raise CommunicationError("La conversación de origen ya no autoriza este encargo.", 403)
        human = next((m for m in conversation['messages'] if m['id'] == source['human_message_id']), None)
        if (not human or human['role'] != 'user' or human['status'] != 'complete'
                or digest(human['content'].encode('utf-8')) != source['human_message_sha256']):
            raise CommunicationError("El mensaje humano de origen no coincide.", 403)
        return human

    def prepare(self, *, human, project, conversation_id, payload, session_identity):
        source = {'mission_id': 'whatsapp:' + human['id'], 'project_id': project['project_id'],
            'binding': project['binding'], 'session_identity': session_identity,
            'conversation_id': conversation_id, 'human_message_id': human['id'],
            'conversation_revision': human['revision'],
            'human_message_sha256': digest(human['content'].encode('utf-8'))}
        current = self._human(project, source)
        recipient = requested_payload(current['content'], payload, self.contacts())
        receipt = {'version': 1, 'source': source, 'payload': payload,
            'project': {k: project[k] for k in ('project_id', 'root', 'binding')},
            'recipient_sha256': digest(encoded(recipient).encode('utf-8'))}
        raw = encoded(receipt).encode('utf-8')
        sha = digest(raw)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (sha + '.json')
        try:
            with path.open('xb') as output:
                output.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise CommunicationError("Conflicto de integridad en el recibo del encargo.", 409) from None
        return {**source, 'send_intent_receipt_sha256': sha}

    def authorize(self, source, payload, project):
        sha = source.get('send_intent_receipt_sha256', '')
        if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha):
            raise CommunicationError("Recibo de intención inválido.", 403)
        path = self.root / (sha + '.json')
        if path.is_symlink():
            raise CommunicationError("El recibo no puede ser un enlace.", 403)
        raw = path.read_bytes()
        if digest(raw) != sha:
            raise CommunicationError("El recibo cambió.", 403)
        receipt = json.loads(raw)
        base = {k: v for k, v in source.items() if k != 'send_intent_receipt_sha256'}
        if (receipt.get('version') != 1 or receipt.get('source') != base or receipt.get('payload') != payload
                or receipt.get('project') != {k: project[k] for k in ('project_id', 'root', 'binding')}
                or base.get('mission_id') != 'whatsapp:' + base['human_message_id']):
            raise CommunicationError("El recibo pertenece a otro encargo o proyecto.", 403)
        human = self._human(project, source)
        recipient = requested_payload(human['content'], payload, self.contacts())
        if digest(encoded(recipient).encode('utf-8')) != receipt.get('recipient_sha256'):
            raise CommunicationError("El destinatario cambió.", 409)
        return {'authorized': True, 'source_sha256': digest(encoded(source).encode('utf-8')),
            'payload_sha256': digest(encoded(payload).encode('utf-8'))}
