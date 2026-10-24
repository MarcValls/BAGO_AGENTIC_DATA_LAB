"""CDP candidate: unique observed owned-profile page, stable per-operation binding."""
import json
import re
import urllib.request
from urllib.parse import urlsplit


TARGET_PROBE = """(() => {
 const shown=s=>[...document.querySelectorAll(s)].some(e=>e.getClientRects().length);
 const blocked=[...document.querySelectorAll('button,[role=button]')].some(e=>e.getClientRects().length&&['Usar aquí','Use here'].includes(e.innerText.trim()));
 return {authenticated:shown('#pane-side')&&shown('[data-testid="chat-list"],#side [role="grid"]'),
   qr:shown('[data-ref] canvas,[data-testid="qrcode"],canvas[aria-label]'),blocked};
})()"""


class CDP:
    def __init__(self, port, target_id=None):
        if type(port) is not int or not 1024 <= port <= 65535 or port == 9222:
            raise RuntimeError("cdp_port_rejected")
        if target_id is not None and (not isinstance(target_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}",target_id)):
            raise RuntimeError("cdp_target_rejected")
        self.port=port
        self.target_id=target_id

    def targets(self):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{self.port}/json/list",timeout=3) as response:
            return json.load(response)

    def _websocket(self,url):
        parsed=urlsplit(url)
        if parsed.scheme!="ws" or parsed.hostname!="127.0.0.1" or parsed.port!=self.port or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError("cdp_endpoint_rejected")
        return url

    def _pages(self):
        pages=[]
        for target in self.targets():
            url=urlsplit(target.get("url",""))
            if target.get("type")!="page" or url.scheme!="https" or url.hostname!="web.whatsapp.com" or url.username or url.password or url.port not in (None,443):
                continue
            target_id=target.get("id")
            if not isinstance(target_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}",target_id):
                continue
            websocket=self._websocket(target.get("webSocketDebuggerUrl",""))
            if urlsplit(websocket).path!="/devtools/page/"+target_id:
                raise RuntimeError("cdp_target_endpoint_mismatch")
            pages.append(target)
        return pages

    def page(self):
        pages=self._pages()
        if self.target_id is not None:
            matches=[p for p in pages if p["id"]==self.target_id]
            if len(matches)!=1:
                raise RuntimeError("bound_whatsapp_page_unavailable")
            return matches[0]["webSocketDebuggerUrl"]
        if not pages:
            raise RuntimeError("whatsapp_page_unavailable")
        if len(pages)==1:
            selected=pages[0]
        else:
            authenticated=[];linking=[];unresolved=False
            for page in pages:
                try:
                    result=self.call("Runtime.evaluate",{"expression":TARGET_PROBE,"returnByValue":True,"awaitPromise":True},websocket=page["webSocketDebuggerUrl"])
                    if result.get("exceptionDetails"):
                        unresolved=True
                        continue
                    value=result.get("result",{}).get("value")
                    if not isinstance(value,dict):
                        unresolved=True
                        continue
                    if value.get("blocked") is True:
                        continue
                    if value.get("blocked") is not False:
                        unresolved=True
                        continue
                    if value.get("authenticated") is True and value.get("qr") is False:
                        authenticated.append(page)
                    elif value.get("qr") is True and value.get("authenticated") is False:
                        linking.append(page)
                    else:
                        unresolved=True
                except Exception:
                    unresolved=True
                    continue
            if unresolved:
                raise RuntimeError("whatsapp_page_ambiguous")
            if len(authenticated)==1:
                selected=authenticated[0]
            elif not authenticated and len(linking)==1:
                selected=linking[0]
            else:
                raise RuntimeError("whatsapp_page_ambiguous")
        self.target_id=selected["id"]
        return selected["webSocketDebuggerUrl"]

    def call(self,method,params=None,websocket=None):
        from websockets.sync.client import connect
        url=self._websocket(websocket or self.page())
        with connect(url,open_timeout=3,close_timeout=1,max_size=4*1024*1024,proxy=None) as socket:
            socket.send(json.dumps({"id":1,"method":method,"params":params or {}}))
            while True:
                result=json.loads(socket.recv(timeout=8))
                if result.get("id")==1:
                    if "error" in result:
                        raise RuntimeError("cdp_command_failed")
                    return result.get("result",{})

    def evaluate(self,expression):
        result=self.call("Runtime.evaluate",{"expression":expression,"returnByValue":True,"awaitPromise":True})
        if result.get("exceptionDetails"):
            raise RuntimeError("dom_probe_failed")
        return result.get("result",{}).get("value")

    def upload(self,paths):
        root=self.call("DOM.getDocument")["root"]["nodeId"]
        node=self.call("DOM.querySelector",{"nodeId":root,"selector":'input[type="file"]:not([accept*="image"])'})["nodeId"]
        if not node:
            raise RuntimeError("upload_input_unavailable")
        self.call("DOM.setFileInputFiles",{"nodeId":node,"files":[str(p) for p in paths]})
