"""Owned visible Brave profile, conservative DOM status and delivery receipts.

No browser cookies, pages or messages are returned in public errors. DOM selectors
are a best effort compatibility boundary, never proof that an action succeeded.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from .cdp import CDP


OUTGOING_ROWS = """[...new Map([...document.querySelectorAll('#main [data-id],#main .message-out')]
 .filter(e=>e.matches('.message-out')||e.querySelector('[data-testid="tail-out"],span[aria-label="Tú:"]'))
 .map(e=>[e.closest('[data-id]')?.getAttribute('data-id'),e])).values()].map(e=>{
 const nodes=[...e.querySelectorAll('[data-testid="selectable-text"],[data-testid="msg-text"],span.selectable-text.copyable-text')];
 const top=nodes.filter(n=>!nodes.some(other=>other!==n&&other.contains(n)));
 const labels=[...e.querySelectorAll('[data-testid="msg-meta"] [aria-label]')].map(x=>x.getAttribute('aria-label').trim());
 const label=labels.find(x=>['Enviado','Entregado','Leído','Sent','Delivered','Read'].includes(x));
 const legacy=!!e.querySelector('[data-icon="msg-check"],[data-icon="msg-dblcheck"]');
 const meta=e.querySelector('[data-pre-plain-text]')?.getAttribute('data-pre-plain-text')||'';
 return {id:e.closest('[data-id]')?.getAttribute('data-id')||null,
 body:top.length===1?top[0].innerText.replace(/\\r\\n/g,'\\n'):null,text:e.innerText,
 ack:!!label||legacy,ack_label:label||(legacy?'legacy-visible-check':null),meta,
 meta_ready:!!meta||!!e.querySelector('[data-testid="msg-meta"]'),pending:!label&&!legacy};})"""

ATTEMPT_OBSERVATION = """/* bago:attempt-observation */ (()=>{
 const a=window.__bagoWhatsAppAttempt;if(!a||document.querySelector('#main')!==a.main)return [];
 a.capture();const rows=a.rows();const last=rows.at(-1)?.id;
 const editor=document.querySelector('[role=dialog] [contenteditable=true][role=textbox],#main footer [contenteditable=true][role=textbox]');
 return [...a.seen.values()].map(r=>({...r,tail:r.id===last,
   composer_cleared:!!editor&&editor.innerText.trim()==='',elapsed_ms:Date.now()-a.clickedAt}));
})()"""


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def process_arguments(pid):
    if os.name == "nt":
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            f"[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); (Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine"],
            capture_output=True, encoding="utf-8", errors="strict", timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.stdout.strip()
    return Path(f"/proc/{int(pid)}/cmdline").read_bytes().decode().replace("\0", " ")


def find_brave():
    candidates = [Path(os.environ.get(key, "__missing__")) / "BraveSoftware/Brave-Browser/Application/brave.exe"
                  for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidates += [Path("/usr/bin/brave-browser"), Path("/usr/bin/brave")]
    return next((str(path) for path in candidates if path.is_file()), None)


def is_link(path):
    return path.is_symlink() or bool(getattr(path.stat(), "st_file_attributes", 0) & 1024)


class WhatsAppSession:
    def __init__(self, state_dir=None):
        default = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "BAGO/AgenticDataLab/whatsapp"
        self.root = Path(state_dir or os.environ.get("BAGO_WHATSAPP_STATE_DIR", default)).resolve()
        self.profile = self.root / "brave-profile"
        self.lock = threading.RLock()

    def _read(self, name):
        try:
            return json.loads((self.root / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _config(self):
        return self._read("config.json")

    def _owner(self):
        owner = self._read("browser.json")
        port = owner.get("port")
        if not isinstance(port, int) or not 1024 <= port <= 65535 or port == 9222:
            return None
        if owner.get("profile") != str(self.profile) or not isinstance(owner.get("pid"), int):
            return None
        try:
            if self.profile.exists() and (is_link(self.profile) or self.profile.resolve() != self.profile):
                return None
            command = process_arguments(owner["pid"])
            # Exact argument boundary, not prefix/substring ownership.
            profile = re.escape(str(self.profile))
            profile_arg = re.search(r'(?:^|\s)"?--user-data-dir=(?:"' + profile + r'"|' + profile + r')"?(?=\s|$)', command, re.I)
            port_arg = re.search(r'(?:^|\s)--remote-debugging-port=' + str(port) + r'(?=\s|$)', command)
            executable = re.match(r'^\s*(?:"([^"]+)"|(\S+))', command)
            name = (executable.group(1) or executable.group(2)).replace("\\", "/").split("/")[-1] if executable else ""
            if not profile_arg or not port_arg or name.lower() not in {"brave.exe", "brave", "brave-browser"}:
                return None
            return owner
        except Exception:
            return None

    def _client(self):
        owner = self._owner()
        if not owner:
            raise RuntimeError("owned_browser_unavailable")
        return CDP(owner["port"])

    def status(self):
        with self.lock:
            try:
                config = self._config()
                state, reason = "disconnected", "browser_closed_or_unowned"
                if not config.get("enabled"):
                    state, reason = "not_configured", "session_disabled"
                elif not find_brave():
                    state, reason = "unavailable", "brave_not_installed"
                elif self._owner():
                    try:
                        observation = self._client().evaluate('''(() => {
                          const shown = s => [...document.querySelectorAll(s)].some(e => e.getClientRects().length);
                          return {authenticated: shown('#pane-side') && shown('[data-testid="chat-list"], #side [role="grid"]'),
                            qr: shown('[data-ref] canvas, [data-testid="qrcode"], canvas[aria-label]')};
                        })()''')
                        if observation and observation.get("authenticated") and not observation.get("qr"):
                            state, reason = "connected", "authenticated_dom_observed"
                        elif observation and observation.get("qr"):
                            state, reason = "linking", "qr_pending"
                        else:
                            state, reason = "unknown", "authentication_not_observed"
                    except Exception:
                        state, reason = "unknown", "probe_failed"
                return {"state": state, "configured": bool(config.get("enabled")), "label": config.get("label", ""),
                        "checked_at": now(), "reason": reason, "browser_available": bool(find_brave()),
                        "persistent_profile": True}
            except Exception:
                return {"state": "unknown", "configured": False, "label": "", "checked_at": now(),
                        "reason": "state_unreadable", "browser_available": bool(find_brave()), "persistent_profile": True}

    def configure(self, label, enabled):
        if not isinstance(label, str) or not label.strip() or len(label) > 100 or type(enabled) is not bool:
            raise ValueError("invalid_configuration")
        with self.lock:
            atomic_json(self.root / "config.json", {"label": label.strip(), "enabled": enabled})
            return self.status()

    def open(self):
        with self.lock:
            if not self._config().get("enabled"):
                raise ValueError("session_not_configured")
            if self._owner():
                return self.status()
            # Refuse unknown running browser records rather than taking over a port/profile.
            old = self._read("browser.json")
            if old.get("pid"):
                try:
                    if process_arguments(old["pid"]):
                        raise ValueError("browser_ownership_unproven")
                except (FileNotFoundError, ProcessLookupError):
                    pass
            executable = find_brave()
            if not executable:
                return self.status()
            self.profile.mkdir(parents=True, exist_ok=True)
            if is_link(self.profile) or self.profile.resolve() != self.profile:
                raise ValueError("profile_reparse_rejected")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            if port == 9222:
                raise ValueError("reserved_port")
            child = subprocess.Popen([executable, f"--user-data-dir={self.profile}",
                f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
                "--no-first-run", "--no-default-browser-check", "https://web.whatsapp.com/"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            atomic_json(self.root / "browser.json", {"pid": child.pid, "port": port, "profile": str(self.profile)})
            return self.status()

    def close(self):
        with self.lock:
            if not self._owner():
                return self.status()
            try:
                client = self._client()
                target = client.targets()[0]
                client.call("Browser.close", websocket=target["webSocketDebuggerUrl"])
            except Exception:
                # Never kill a PID after failed/uncertain ownership checks.
                return {**self.status(), "state": "unknown", "reason": "close_not_observed"}
            return self.status()

    def send(self, phone, text, attachments, operation_id):
        if not re.fullmatch(r"\+[1-9][0-9]{6,14}", phone or "") or not isinstance(text, str):
            raise ValueError("invalid_message")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", operation_id or "") or (not text.strip() and not attachments):
            raise ValueError("invalid_operation")
        with self.lock:
            receipt_path = self.root / "operations" / (operation_id + ".json")
            payload = {"phone": phone, "text": text, "attachments": []}
            files = []
            for item in attachments:
                path = Path(item)
                if not path.is_file() or any(is_link(parent) for parent in (path, *path.parents)) or path.stat().st_size > 20*1024*1024:
                    raise ValueError("attachment_invalid")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                files.append((path.resolve(), digest))
                payload["attachments"].append({"path": str(path.resolve()), "sha256": digest})
            identity = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if receipt_path.exists():
                old = json.loads(receipt_path.read_text(encoding="utf-8"))
                if old.get("identity") != identity:
                    raise ValueError("operation_payload_mismatch")
                return {key: value for key, value in old.items() if key != "identity"}
            result = {"status": "failed", "operation_id": operation_id, "observed_at": now(), "reason": "session_not_connected"}
            if self.status()["state"] != "connected":
                return result
            # Durable reservation BEFORE navigation/effect; exclusive across service processes.
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            pending = {**result, "status": "uncertain", "reason": "attempt_in_progress_or_interrupted", "identity": identity}
            try:
                with receipt_path.open("x", encoding="utf-8") as output:
                    json.dump(pending, output)
                    output.flush()
                    os.fsync(output.fileno())
            except FileExistsError:
                return {**result, "status": "uncertain", "reason": "operation_already_claimed"}
            try:
                client = self._client()
                client.call("Page.navigate", {"url": "https://web.whatsapp.com/send?" + urlencode({"phone": phone[1:]})})
                # Require visible exact phone, including a saved contact's fresh
                # public contact-info drawer; a name never authorizes a send.
                ready = False
                for _ in range(20):
                    if self._recipient_matches(client, phone):
                        ready = True
                        break
                    time.sleep(.5)
                if not ready:
                    result["reason"] = "exact_recipient_not_observed"
                else:
                    before = client.evaluate("/* bago:outgoing-baseline */ " + OUTGOING_ROWS + ".map(row=>row.id).filter(Boolean)") or []
                    immutable = []
                    for index, (path, digest) in enumerate(files):
                        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                            raise RuntimeError("attachment_changed")
                        snapshot = self.root / "operations" / operation_id / str(index) / path.name
                        snapshot.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, snapshot)
                        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
                            raise RuntimeError("attachment_changed")
                        immutable.append((snapshot, digest))
                    self._compose(client, text, immutable)
                    for path, digest in immutable:
                        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                            raise RuntimeError("attachment_changed")
                    if not self._recipient_matches(client, phone):
                        raise RuntimeError("recipient_changed_before_send")
                    self._arm_attempt(client, operation_id, text, before)
                    # From this boundary onwards failures are uncertain, never retried.
                    result.update(status="uncertain", reason="acknowledgement_not_observed")
                    self._click_once(client, operation_id, text)
                    for _ in range(20):
                        observed = client.evaluate(ATTEMPT_OBSERVATION) or []
                        matches = [row for row in observed if row.get("id") and row["id"] not in before and row.get("ack") is True
                                   and row.get("pending_seen") is True and row.get("after_click") is True and row.get("tail") is True
                                   and row.get("composer_cleared") is True and row.get("current_minute") is True and isinstance(row.get("elapsed_ms"), (int, float))
                                   and 0 <= row["elapsed_ms"] <= 15000 and (not text or row.get("body") == text)
                                   and all(path.name in row.get("text", "") for path, _ in files)]
                        if len(matches) == 1:
                            match = matches[0]
                            if self._recipient_matches(client, phone):
                                result.update(status="sent", reason="new_outgoing_message_acknowledged", message_id=match["id"], acknowledgement=match.get("ack_label"))
                                break
                        time.sleep(.5)
            except Exception:
                result.update(status="uncertain", reason="transport_interrupted_or_dom_unsupported")
            finally:
                try:
                    client.evaluate("/* bago:attempt-cleanup */ (()=>{const a=window.__bagoWhatsAppAttempt;if(a)a.observer.disconnect();delete window.__bagoWhatsAppAttempt;return true;})()")
                except Exception:
                    pass
            result["observed_at"] = now()
            atomic_json(receipt_path, {**result, "identity": identity})
            return result

    def _recipient_matches(self, client, phone):
        header_script = "document.querySelector('#main header')?.innerText || ''"
        header = client.evaluate(header_script)
        if not isinstance(header, str) or not header.strip():
            return False
        if re.sub(r"[^+0-9]", "", header) == phone:
            return True
        # Scope the close control to the observed contact drawer, never the
        # unrelated notification's Cerrar button (data-tab=4).
        close = """/* bago:contact-close */ (()=>{const d=document.querySelector('[data-testid="chat-info-drawer"]');
          if(!d||!d.getClientRects().length)return true;
          const b=document.querySelector('[data-testid="drawer-right"] button[aria-label="Cerrar"][data-tab="2"]');
          if(!b)return false;b.click();return true;})()"""
        if client.evaluate(close) is not True:
            return False
        opened = client.evaluate("""/* bago:contact-open */ (()=>{const e=document.querySelector('#main [data-testid="conversation-info-header"]');
          if(!e)return false;e.click();return true;})()""")
        if opened is not True:
            return False
        drawer = None
        for _ in range(10):
            drawer = client.evaluate("""/* bago:contact-phone */ (()=>{const d=document.querySelector('[data-testid="chat-info-drawer"]');
              return d&&d.getClientRects().length?d.innerText:null;})()""")
            if isinstance(drawer, str) and drawer.strip():
                break
            time.sleep(.1)
        closed = client.evaluate(close)
        if not isinstance(drawer, str) or closed is not True:
            return False
        numbers = []
        for line in drawer.splitlines():
            line = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", line).strip()
            if re.fullmatch(r"\+[0-9][0-9 ()-]{6,}", line):
                numbers.append(re.sub(r"[^+0-9]", "", line))
        return len(numbers) == 1 and numbers[0] == phone

    def _arm_attempt(self, client, operation_id, text, before):
        script = """/* bago:attempt-arm */ (()=>{
          const old=window.__bagoWhatsAppAttempt;if(old)old.observer.disconnect();
          const main=document.querySelector('#main');if(!main)throw Error();
          const config=__BAGO_CONFIG__;
          const a={main,operation:config.operation,expected:config.text,rows:()=>__BAGO_ROWS__,seen:new Map(),clicked:false,clickedAt:null,
            header:document.querySelector('#main [data-testid="conversation-info-header"]')||document.querySelector('#main header'),baseline:new Set(config.before)};
          for(const r of a.rows())if(r.id)a.baseline.add(r.id);
          a.anchor=a.rows().at(-1)?.id;
          a.capture=()=>{if(!a.clicked)return;const rows=a.rows();const anchor=rows.findIndex(r=>r.id===a.anchor);
            for(let i=0;i<rows.length;i++){const r=rows[i];if(!r.id||a.baseline.has(r.id)||(a.anchor&&(anchor<0||i<=anchor)))continue;
              const prev=a.seen.get(r.id);const prefix=d=>'['+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+', '+String(d.getDate()).padStart(2,'0')+'/'+String(d.getMonth()+1).padStart(2,'0')+'/'+d.getFullYear()+']';
              const recent=!!r.meta&&(r.meta.startsWith(prefix(new Date(a.clickedAt)))||r.meta.startsWith(prefix(new Date(a.clickedAt+15000))));
              a.seen.set(r.id,{...r,after_click:true,current_minute:recent,pending_seen:(!!r.pending&&!!r.meta_ready&&recent)||!!prev?.pending_seen});}};
          a.observer=new MutationObserver(a.capture);a.observer.observe(main,{subtree:true,childList:true,attributes:true,attributeFilter:['data-icon','data-id','class']});
          window.__bagoWhatsAppAttempt=a;return true;})()"""
        script = script.replace("__BAGO_ROWS__", OUTGOING_ROWS).replace("__BAGO_CONFIG__", json.dumps({"operation":operation_id,"text":text,"before":before}))
        if client.evaluate(script) is not True:
            raise RuntimeError("attempt_observer_unavailable")

    def _click_once(self, client, operation_id, text):
        script = """/* bago:attempt-click */ (()=>{const a=window.__bagoWhatsAppAttempt;const config=__BAGO_CONFIG__;
          const e=document.querySelector('[role=dialog] [contenteditable=true][role=textbox],#main footer [contenteditable=true][role=textbox]');
          const header=document.querySelector('#main [data-testid="conversation-info-header"]')||document.querySelector('#main header');
          if(!a||a.clicked||a.operation!==config.operation||document.querySelector('#main')!==a.main||header!==a.header||!e||e.innerText.replace(/\\r\\n/g,'\\n')!==config.text)throw Error();
          e.focus();if(document.activeElement!==e)throw Error();
          a.clicked=true;a.clickedAt=Date.now();return true;})()"""
        script = script.replace("__BAGO_CONFIG__", json.dumps({"operation":operation_id,"text":text}))
        if client.evaluate(script) is not True:
            raise RuntimeError("send_focus_not_observed")
        # Scoped CDP input to the validated editor, never a global OS keypress.
        # Exactly one Enter keyDown; no fallback/retry after an uncertain effect.
        client.call("Input.dispatchKeyEvent", {"type":"keyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13})
        client.call("Input.dispatchKeyEvent", {"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13})
        client.evaluate("/* bago:attempt-capture */ (()=>{const a=window.__bagoWhatsAppAttempt;if(a)a.capture();return true;})()")

    def _compose(self, client, text, files):
        if files:
            client.evaluate("(() => { const b=document.querySelector('#main [data-icon=plus-rounded],#main [data-icon=clip]'); if(!b) throw Error(); b.closest('button,[role=button]').click(); return true; })()")
            client.upload([path for path, _ in files])
            time.sleep(1)
        if text:
            client.evaluate("(() => { const e=document.querySelector('[role=dialog] [contenteditable=true][role=textbox],#main footer [contenteditable=true][role=textbox]'); if(!e) throw Error(); e.focus(); return true; })()")
            client.call("Input.insertText", {"text": text})
