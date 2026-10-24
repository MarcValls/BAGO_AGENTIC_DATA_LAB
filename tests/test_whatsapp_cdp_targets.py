import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest

import src.whatsapp.cdp as module


def page(identity,**fields):
    return {"id":identity,"type":"page","url":"https://web.whatsapp.com/","webSocketDebuggerUrl":f"ws://127.0.0.1:9333/devtools/page/{identity}",**fields}


def client(pages,observations=None,target_id=None):
    c=module.CDP(9333,target_id)
    c.targets=Mock(return_value=pages)
    def probe(*args,**kwargs):
        identity=kwargs["websocket"].rsplit("/",1)[1]
        value=observations[identity]
        if isinstance(value,Exception):raise value
        return {"result":{"value":value}}
    c.call=Mock(side_effect=probe)
    return c


AUTH={"authenticated":True,"qr":False,"blocked":False}
QR={"authenticated":False,"qr":True,"blocked":False}
BLOCKED={"authenticated":False,"qr":False,"blocked":True}


@pytest.mark.parametrize("reverse",[False,True])
def test_unique_auth_not_first_blocked(reverse):
    pages=[page("blocked"),page("auth")]
    c=client(list(reversed(pages)) if reverse else pages,{"blocked":BLOCKED,"auth":AUTH})
    assert c.page().endswith("/auth") and c.target_id=="auth"
    assert all(a.args[0]=="Runtime.evaluate" for a in c.call.call_args_list)


def test_unique_qr_without_auth():
    c=client([page("blocked"),page("qr")],{"blocked":BLOCKED,"qr":QR})
    assert c.page().endswith("/qr")


@pytest.mark.parametrize("values",[(AUTH,AUTH),(QR,QR),(BLOCKED,BLOCKED),({},{}),(RuntimeError(),BLOCKED),(AUTH,RuntimeError()),(AUTH,{})])
def test_ambiguity_or_unknown_refused(values):
    c=client([page("a"),page("b")],dict(zip(("a","b"),values)))
    with pytest.raises(RuntimeError,match="ambiguous"):c.page()
    assert c.target_id is None


def test_unique_auth_has_priority_over_qr():
    c=client([page("auth"),page("qr")],{"auth":AUTH,"qr":QR})
    assert c.page().endswith("/auth")


def test_single_page_binding_is_stable_and_never_falls_back():
    c=client([page("a")]);assert c.page().endswith("/a")
    c.targets.return_value=[page("b")]
    with pytest.raises(RuntimeError,match="bound_whatsapp_page_unavailable"):c.page()


def test_bound_domain_change_refused_without_fallback():
    c=client([page("a")],target_id="a")
    c.targets.return_value=[page("a",url="https://example.com/"),page("b")]
    with pytest.raises(RuntimeError,match="bound_whatsapp_page_unavailable"):c.page()


def test_explicit_target_exact_no_probe():
    c=client([page("a"),page("b")],target_id="b")
    assert c.page().endswith("/b")
    c.call.assert_not_called()


@pytest.mark.parametrize("url",["ws://example.com:9333/devtools/page/a","ws://127.0.0.1:9222/devtools/page/a","ws://user@127.0.0.1:9333/devtools/page/a","ws://127.0.0.1:9333/devtools/page/a?x=1","ws://127.0.0.1:9333/devtools/page/other"])
def test_foreign_endpoint_refused(url):
    c=client([page("a",webSocketDebuggerUrl=url)])
    with pytest.raises(RuntimeError):c.page()
    c.call.assert_not_called()


@pytest.mark.parametrize("port",[9222,80,True,"9333",65536])
def test_invalid_or_personal_port_refused(port):
    with pytest.raises(RuntimeError):module.CDP(port)


def test_other_site_never_selected():
    c=client([page("a",url="https://web.whatsapp.com.evil.example/")])
    with pytest.raises(RuntimeError,match="unavailable"):c.page()


def test_upload_uses_same_bound_client_methods(tmp_path):
    c=module.CDP(9333,"a");c.call=Mock(side_effect=[{"root":{"nodeId":1}},{"nodeId":2},{}])
    c.upload([tmp_path/"fixture.pdf"])
    assert [a.args[0] for a in c.call.call_args_list]==["DOM.getDocument","DOM.querySelector","DOM.setFileInputFiles"]
