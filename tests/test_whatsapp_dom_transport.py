"""Observed public DOM shapes in synthetic jsdom; never touches a browser/port."""
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
import src.whatsapp.session as module

PHONE = "+34600000000"  # Synthetic only.


def attempt_row(**changes):
    return {"id":"new","body":"Hola","text":"Hola","ack":True,"ack_label":"Enviado","pending_seen":True,
            "after_click":True,"tail":True,"composer_cleared":True,"current_minute":True,"elapsed_ms":100,**changes}


@pytest.fixture
def transport(tmp_path, monkeypatch):
    s = module.WhatsAppSession(tmp_path)
    monkeypatch.setattr(s,"status",lambda:{"state":"connected"})
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    c=Mock()
    def evaluate(script):
        if script == "document.querySelector('#main header')?.innerText || ''":
            return "Saved synthetic contact\nonline"
        if "bago:contact-phone" in script:
            return "Info. del contacto\nSaved synthetic contact\n+34 600 00 00 00"
        if "bago:outgoing-baseline" in script:
            return ["old"]
        if "bago:attempt-observation" in script:
            return [attempt_row()]
        return True
    c.evaluate.side_effect=evaluate
    monkeypatch.setattr(s,"_client",lambda:c)
    monkeypatch.setattr(s,"_compose",Mock())
    return s,c


def test_saved_contact_info_exact_phone_and_single_scoped_enter(transport):
    s,c=transport
    result=s.send(PHONE,"Hola",[],"saved-contact")
    assert result["status"]=="sent" and result["acknowledgement"]=="Enviado"
    keys=[args.args for args in c.call.call_args_list if args.args[0]=="Input.dispatchKeyEvent"]
    assert [a[1]["type"] for a in keys]==["keyDown","keyUp"]
    assert all(a[1]["key"]=="Enter" for a in keys)
    assert any("chat-info-drawer" in a.args[0] for a in c.evaluate.call_args_list)


@pytest.mark.parametrize("drawer", ["Saved contact", "Info\n+34 699 99 99 99", "Info\n+34 600 00 00 00\n+34 699 99 99 99", None])
def test_wrong_missing_or_ambiguous_phone_never_composes(transport,drawer):
    s,c=transport;base=c.evaluate.side_effect
    c.evaluate.side_effect=lambda script:drawer if "bago:contact-phone" in script else base(script)
    assert s.send(PHONE,"Hola",[],"bad-phone")["status"]=="failed"
    s._compose.assert_not_called()
    assert not any(a.args[0]=="Input.dispatchKeyEvent" for a in c.call.call_args_list)


@pytest.mark.parametrize("change", [{"body":"Prefix Hola"},{"body":"Hola suffix"},{"body":"Hola\n"},{"pending_seen":False},
    {"current_minute":False},{"composer_cleared":False},{"tail":False},{"ack":False},{"id":"old"},{"id":None},
    {"elapsed_ms":16000},{"after_click":False}])
def test_unrelated_or_uncorrelated_outgoing_never_passes(transport,change):
    s,c=transport;base=c.evaluate.side_effect
    c.evaluate.side_effect=lambda script:[attempt_row(**change)] if "bago:attempt-observation" in script else base(script)
    assert s.send(PHONE,"Hola",[],"uncertain")["status"]=="uncertain"
    assert len([a for a in c.call.call_args_list if a.args[0]=="Input.dispatchKeyEvent" and a.args[1]["type"]=="keyDown"])==1


def test_recipient_changed_after_composition_is_not_sent(transport,monkeypatch):
    s,c=transport
    monkeypatch.setattr(s,"_recipient_matches",Mock(side_effect=[True,False]))
    assert s.send(PHONE,"Hola",[],"changed")["status"]=="uncertain"
    assert not any(a.args[0]=="Input.dispatchKeyEvent" for a in c.call.call_args_list)


def test_recipient_changes_after_ack_not_claimed_sent(transport,monkeypatch):
    s,c=transport
    checks=iter([True,True]+[False]*20)
    monkeypatch.setattr(s,"_recipient_matches",lambda *_:next(checks))
    assert s.send(PHONE,"Hola",[],"changed-after")["status"]=="uncertain"


def node_dom(scripts, mode="valid", text="Hola"):
    root=Path(__file__).resolve().parents[1]
    node=shutil.which("node")
    assert node and (root/"frontend/node_modules/jsdom").is_dir(), "Declared frontend jsdom tooling is required for DOM fixtures"
    harness=r'''
const {JSDOM}=require(process.argv[1]);let input='';process.stdin.on('data',d=>input+=d);process.stdin.on('end',async()=>{
 const p=JSON.parse(input);const dom=new JSDOM('<main id="main"><header><div data-testid="conversation-info-header">Saved contact</div></header><div data-id="old"><div data-testid="tail-out"></div><span data-testid="selectable-text">Old</span><span data-testid="msg-meta" aria-label="Enviado"></span></div><footer><div contenteditable="true" role="textbox" tabindex="0"></div></footer></main>',{runScripts:'outside-only'});
 const w=dom.window,d=w.document;Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent},set(v){this.textContent=v}});
 Object.defineProperty(w.HTMLElement.prototype,'getClientRects',{value(){return this.style.display==='none'?[]:[{}]}});
 let drawerCloses=0,notificationCloses=0;
 const right=d.createElement('div');right.setAttribute('data-testid','drawer-right');right.innerHTML='<div data-testid="chat-info-drawer" style="display:none">Info. del contacto\nSaved synthetic contact\n+34 600 00 00 00</div><button aria-label="Cerrar" data-tab="2">Close contact</button>';
 d.body.append(right);const drawer=right.querySelector('[data-testid=chat-info-drawer]');
 right.querySelector('button').onclick=()=>{drawer.style.display='none';drawerCloses++;};
 const notification=d.createElement('button');notification.setAttribute('aria-label','Cerrar');notification.setAttribute('data-tab','4');notification.onclick=()=>notificationCloses++;d.body.append(notification);
 d.querySelector('[data-testid=conversation-info-header]').onclick=()=>drawer.style.display='block';
 const editor=d.querySelector('[contenteditable]');editor.innerText=p.text;
 const minute=()=>{const t=new Date();return '['+String(t.getHours()).padStart(2,'0')+':'+String(t.getMinutes()).padStart(2,'0')+', '+String(t.getDate()).padStart(2,'0')+'/'+String(t.getMonth()+1).padStart(2,'0')+'/'+t.getFullYear()+']';};
 editor.addEventListener('keydown',e=>{if(e.key!=='Enter')return;
   const row=d.createElement('div');row.setAttribute('data-id','AC-synthetic');row.setAttribute('data-testid','conv-msg-AC-synthetic');
   row.innerHTML='<div data-testid="tail-out"></div><span aria-label="Tú:"></span><div class="copyable-text"><span data-testid="selectable-text"></span></div><div data-testid="msg-meta"><span aria-label=""></span></div>';
   row.querySelector('[data-pre-plain-text],.copyable-text').setAttribute('data-pre-plain-text',(p.mode==='oldtime'?'[12:15, 21/10/2026]':minute())+' Sender: ');
   row.querySelector('[data-testid=selectable-text]').textContent=p.mode==='wrongtext'?'Prefix '+p.text:p.text;
   if(p.mode==='history')row.querySelector('[aria-label=""]').setAttribute('aria-label',' Enviado ');
   d.querySelector('footer').before(row);if(p.mode!=='uncleared')editor.innerText='';
   if(p.mode!=='noack')setTimeout(()=>row.querySelector('[data-testid=msg-meta] span').setAttribute('aria-label',' Entregado '),10);
 });
 const outputs=[];try{for(const action of p.scripts){if(action.kind==='eval'){outputs.push(w.eval(action.script));}else if(action.method==='Input.dispatchKeyEvent'){editor.dispatchEvent(new w.KeyboardEvent(action.params.type==='keyDown'?'keydown':'keyup',{key:'Enter',bubbles:true}));}await new Promise(r=>setTimeout(r,1));}await new Promise(r=>setTimeout(r,30));outputs.push(w.eval(p.observe));console.log(JSON.stringify({outputs,drawer_closes:drawerCloses,notification_closes:notificationCloses}));}catch(e){console.log(JSON.stringify({error:e.name}));}finally{dom.window.close();}
});'''
    result=subprocess.run([node,"-e",harness,str(root/"frontend/node_modules/jsdom")],input=json.dumps({"scripts":scripts,"mode":mode,"text":text,"observe":module.ATTEMPT_OBSERVATION}),text=True,encoding="utf-8",capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


def scripts_for(s,text="Hola"):
    scripts=[];c=Mock()
    c.evaluate.side_effect=lambda script:scripts.append({"kind":"eval","script":script}) or True
    c.call.side_effect=lambda method,params:scripts.append({"kind":"call","method":method,"params":params}) or {}
    s._arm_attempt(c,"fixture",text,["old"])
    s._click_once(c,"fixture",text)
    return scripts


def test_real_dom_shape_without_message_out_has_exact_body_and_ancestor_id(transport):
    s,_=transport
    out=node_dom(scripts_for(s))
    assert "error" not in out,out
    row=out["outputs"][-1][0]
    assert row["id"]=="AC-synthetic" and row["body"]=="Hola" and row["ack_label"]=="Entregado"
    assert all(row[k] for k in ("pending_seen","current_minute","after_click","composer_cleared","tail"))


@pytest.mark.parametrize("mode,field",[("history","pending_seen"),("oldtime","current_minute"),("uncleared","composer_cleared"),("noack","ack")])
def test_dom_rejects_recent_preacked_history_old_dates_and_missing_effect(transport,mode,field):
    s,_=transport
    out=node_dom(scripts_for(s),mode)
    assert "error" not in out,out
    assert out["outputs"][-1][0][field] is False


def test_template_tokens_in_text_are_not_replaced(transport):
    s,_=transport;text='TEXT ROWS BASELINE OPERATION __BAGO_CONFIG__ " ñ'
    out=node_dom(scripts_for(s,text),text=text)
    assert "error" not in out,out
    assert out["outputs"][-1][0]["body"]==text


def test_contact_drawer_dom_is_scoped_and_never_closes_notification(transport):
    s,_=transport;scripts=[];c=Mock()
    def evaluate(script):
        scripts.append({"kind":"eval","script":script})
        if script=="document.querySelector('#main header')?.innerText || ''":
            return "Saved synthetic contact\nonline"
        if "bago:contact-phone" in script:
            return "Info. del contacto\n+34 600 00 00 00"
        return True
    c.evaluate.side_effect=evaluate
    assert s._recipient_matches(c,PHONE)
    out=node_dom(scripts)
    assert "error" not in out,out
    assert "+34 600 00 00 00" in out["outputs"][3]
    assert out["drawer_closes"]==1 and out["notification_closes"]==0


def test_online_header_changes_do_not_replace_recipient_identity(transport):
    s,_=transport;scripts=scripts_for(s)
    scripts.insert(1,{"kind":"eval","script":"document.querySelector('[data-testid=conversation-info-header]').textContent='Saved contact typing…'"})
    out=node_dom(scripts)
    assert "error" not in out,out
    assert out["outputs"][-1][0]["ack"] is True


def test_changed_composer_is_blocked_before_enter(transport):
    s,_=transport
    out=node_dom(scripts_for(s),text="Hola plus unreviewed content")
    assert out.get("error")=="Error"
