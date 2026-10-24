import json
from unittest.mock import Mock

import pytest

from src.whatsapp import WhatsAppSession
from src.whatsapp.cdp import CDP


PHONE = "+34600000000"  # Synthetic test fixture; transport is always injected.


@pytest.fixture
def transport(tmp_path, monkeypatch):
    session = WhatsAppSession(tmp_path)
    monkeypatch.setattr(session, "status", lambda: {"state": "connected"})
    monkeypatch.setattr("src.whatsapp.session.time.sleep", lambda _: None)
    client = Mock()
    def evaluate(expression):
        if expression == "document.querySelector('#main header')?.innerText || ''":
            return PHONE
        if "bago:outgoing-baseline" in expression:
            return ["old"]
        if "bago:attempt-observation" in expression:
            return [{"id":"new","body":"Hola","text":"Hola informe.pdf","ack":True,"ack_label":"Enviado",
                     "pending_seen":True,"after_click":True,"tail":True,"composer_cleared":True,"current_minute":True,"elapsed_ms":100}]
        return True
    client.evaluate.side_effect = evaluate
    monkeypatch.setattr(session, "_client", lambda: client)
    monkeypatch.setattr(session, "_compose", Mock())
    return session, client


def test_positive_receipt_and_replay(transport):
    session, client = transport
    result = session.send(PHONE, "Hola", [], "op1")
    assert result["status"] == "sent" and result["message_id"] == "new"
    before = client.call.call_count
    assert session.send(PHONE, "Hola", [], "op1") == result
    assert client.call.call_count == before
    with pytest.raises(ValueError, match="payload_mismatch"):
        session.send(PHONE, "Cambio", [], "op1")


def test_pdf_attachment(transport, tmp_path):
    session, _ = transport
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.7 synthetic fixture")
    assert session.send(PHONE, "Hola", [pdf], "pdf1")["status"] == "sent"
    assert session._compose.call_args[0][2][0][0].name == "informe.pdf"


@pytest.mark.parametrize("ack,message_id", [(False, "new"), (True, "old"), (True, None)])
def test_click_without_new_ack_is_uncertain(transport, ack, message_id):
    session, client = transport
    base = client.evaluate.side_effect
    client.evaluate.side_effect = lambda expression: [{"id":message_id,"body":"Hola","text":"Hola","ack":ack,
        "pending_seen":True,"after_click":True,"tail":True,"composer_cleared":True,"current_minute":True,"elapsed_ms":100}] if "bago:attempt-observation" in expression else base(expression)
    assert session.send(PHONE, "Hola", [], "op1")["status"] == "uncertain"


def test_wrong_recipient_blocks_composition(transport):
    session, client = transport
    client.evaluate.return_value = "+34999999999"
    client.evaluate.side_effect = None
    assert session.send(PHONE, "Hola", [], "op1")["status"] == "failed"
    session._compose.assert_not_called()


def test_disconnected_no_effect(transport, monkeypatch):
    session, client = transport
    monkeypatch.setattr(session, "status", lambda: {"state": "disconnected"})
    assert session.send(PHONE, "Hola", [], "op1")["status"] == "failed"
    client.call.assert_not_called()


def test_interrupted_receipt_never_retries(transport):
    session, client = transport
    client.call.side_effect = RuntimeError("SECRET")
    result = session.send(PHONE, "Hola", [], "op1")
    assert result["status"] == "uncertain" and "SECRET" not in json.dumps(result)
    count = client.call.call_count
    other = WhatsAppSession(session.root)
    assert other.send(PHONE, "Hola", [], "op1") == result
    assert client.call.call_count == count


def test_missing_attachment_invalid(transport, tmp_path):
    session, client = transport
    with pytest.raises(ValueError, match="attachment_invalid"):
        session.send(PHONE, "Hola", [tmp_path / "missing.pdf"], "op1")
    client.call.assert_not_called()


def test_invalid_phone_and_operation(transport):
    session, client = transport
    with pytest.raises(ValueError):
        session.send("contactname", "Hola", [], "op1")
    with pytest.raises(ValueError):
        session.send(PHONE, "Hola", [], "../outside")
    client.call.assert_not_called()


def test_cdp_rejects_non_loopback():
    with pytest.raises(RuntimeError, match="endpoint_rejected"):
        CDP(9333).call("Browser.close", websocket="ws://example.com:9333/x")


def test_snapshot_mutation_cannot_be_reported_sent(transport, tmp_path):
    session, _ = transport
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF initial")
    def mutate(client, text, files):
        files[0][0].write_bytes(b"altered")
    session._compose.side_effect = mutate
    assert session.send(PHONE, "Hola", [pdf], "mutation")["status"] == "uncertain"


def test_attachment_is_snapshotted(transport, tmp_path):
    session, _ = transport
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF initial")
    def mutate_original(client, text, files):
        assert files[0][0] != pdf
        pdf.write_bytes(b"changed original")
    session._compose.side_effect = mutate_original
    assert session.send(PHONE, "Hola", [pdf], "snapshot")["status"] == "sent"


def test_persistence_failure_stops_before_effect(transport, monkeypatch):
    session, client = transport
    original = type(session.root).open
    def fail(self, *args, **kwargs):
        if str(self).endswith("op1.json") and args and args[0] == "x":
            raise PermissionError("secret")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(type(session.root), "open", fail)
    with pytest.raises(PermissionError):
        session.send(PHONE, "Hola", [], "op1")
    client.call.assert_not_called()
