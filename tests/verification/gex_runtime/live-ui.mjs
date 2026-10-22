import { chromium } from 'file:///C:/Users/AMTEC_Terminal_1%C2%BA/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, execFileSync} from 'node:child_process';
const root=process.cwd(), out=path.join(root,'output/playwright/gex-runtime-20261020');
fs.mkdirSync(out,{recursive:true});
const state=path.join(root,'.worktrees/gex-runtime-20261020/state');
const cred=JSON.parse(fs.readFileSync(path.join(state,'operator-credential.json'),'utf8'));
const base='http://127.0.0.1:8181', agent='agent_308e34fa4d244dd2a2efadf00bc943dd';
let child,browser; const identities=[], errors=[];
const logfile=fs.openSync(path.join(out,'server.log'),'a');
const hash=f=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex');
const sourceFiles=['src/api/server.py','src/api/gex_routes.py','src/execution/gex_control.py','src/execution/gex_service.py','src/execution/ledger/sqlite_ledger.py','src/execution/permit/permit_v1.py','src/execution/adapters/fixture_read.py','src/execution/adapters/fixture_observer.py','frontend/src/App.tsx','frontend/src/components/GovernedFixtureRunner.tsx','src/providers/ollama.py','frontend/dist/index.html'];
const manifest={}; for(const f of sourceFiles) if(fs.existsSync(path.join(root,f)))manifest[f]=hash(f);
for(const f of fs.readdirSync(path.join(root,'frontend/dist/assets')))manifest['frontend/dist/assets/'+f]=hash('frontend/dist/assets/'+f);
fs.writeFileSync(path.join(out,'candidate-manifest.json'),JSON.stringify({head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),files:manifest},null,2));
async function start(){
  child=spawn('python',['-m','src.api.server'],{cwd:root,windowsHide:true,env:{...process.env,BAGO_GEX_STATE_DIR:state,BAGO_GEX_WORKSPACE_ROOT:path.join(root,'.worktrees/gex-runtime-20261020/workspace'),BAGO_API_PORT:'8181',BAGO_API_HOST:'127.0.0.1'},stdio:['ignore',logfile,logfile]});
  const pid=child.pid; identities.push({pid,started_at:new Date().toISOString(),command:'python -m src.api.server',port:8181});
  for(let i=0;i<90;i++){if(child.exitCode!==null)throw Error('Owned server exited '+child.exitCode);try{const r=await fetch(base+'/api/gex/status');const v=await r.json(); if(v.state==='READY'){identities.at(-1).status=v;return;}}catch{} await new Promise(r=>setTimeout(r,500));}
  throw Error('owned server did not become READY');
}
async function stop(){if(!child||child.exitCode!==null)return;const current=child;current.kill();await new Promise((r,j)=>{current.once('exit',r);setTimeout(()=>j(Error('Owned child failed to stop')),10000)});identities.at(-1).stopped_at=new Date().toISOString();child=null;}
async function auth(page){await page.getByLabel('ID del agente guardado',{exact:true}).fill(agent);await page.getByLabel('Clave de operador',{exact:true}).fill(cred.api_key);const ready=page.waitForResponse(r=>r.url()===base+'/api/gex/sessions'&&r.request().method()==='POST');await page.getByRole('button',{name:'Crear sesión',exact:true}).click();const r=await ready;if(r.status()!==201)throw Error('Session status '+r.status());await page.getByRole('button',{name:'Revocar y borrar sesión'}).waitFor();if(await page.getByLabel('Clave de operador',{exact:true}).count())throw Error('Operator password field still mounted');}
async function navigate(page){await page.goto(base);await page.getByRole('button',{name:'Agent Runs',exact:true}).click();await page.getByRole('heading',{name:/fixture|gobernada|gobernado/i}).first().waitFor();}
try{
  const pre=await fetch(base+'/api/gex/status').then(()=>true).catch(()=>false);if(pre)throw Error('Port8181 already occupied; refusing');
  await start();browser=await chromium.launch({headless:false});const context=await browser.newContext({viewport:{width:1480,height:1100}});const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e.message).slice(0,200)));
  await navigate(page);await auth(page);await page.screenshot({path:path.join(out,'01-authenticated.png'),fullPage:true});
  const proposed=page.waitForResponse(r=>r.url()===base+'/api/gex/requests'&&r.request().method()==='POST',{timeout:65000});
  await page.getByRole('button',{name:'Solicitar propuesta',exact:true}).click();const response=await proposed;const proposal=await response.json();fs.writeFileSync(path.join(out,'proposal.json'),JSON.stringify(proposal,null,2));if(response.status()!==201||proposal.state!=='AWAITING_APPROVAL')throw Error('Actual provider proposal failed '+response.status()+' '+(proposal.error?.code||proposal.detail?.code||proposal.state));
  await page.getByRole('button',{name:'Aprobar solicitud exacta y ejecutar ahora',exact:true}).waitFor();await page.screenshot({path:path.join(out,'02-exact-review.png'),fullPage:true});
  const decision=page.waitForResponse(r=>r.url()===base+'/api/gex/requests/'+proposal.request_id+'/decision');await page.getByRole('button',{name:'Aprobar solicitud exacta y ejecutar ahora',exact:true}).click();const d=await decision;const done=await d.json();fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(done,null,2));if(d.status()!==200||done.state!=='SUCCEEDED'||!done.integrity.receipt_verified)throw Error('Decision did not verify '+d.status()+' '+done.state);
  await page.screenshot({path:path.join(out,'03-verified-result.png'),fullPage:true});fs.writeFileSync(path.join(out,'03-dom.txt'),await page.locator('body').innerText());
  await context.close();await stop();await start();const ctx2=await browser.newContext({viewport:{width:1480,height:1100}});const p2=await ctx2.newPage();await navigate(p2);await auth(p2);await p2.getByLabel('ID de solicitud para recuperar',{exact:true}).fill(proposal.request_id);const loaded=p2.waitForResponse(r=>r.url()===base+'/api/gex/requests/'+proposal.request_id&&r.request().method()==='GET');await p2.getByRole('button',{name:'Recargar estado durable',exact:true}).click();const recovery=await (await loaded).json();fs.writeFileSync(path.join(out,'restart-readback.json'),JSON.stringify(recovery,null,2));if(recovery.state!=='SUCCEEDED'||!recovery.integrity.receipt_verified)throw Error('Restart readback failed');await p2.screenshot({path:path.join(out,'04-restart-readback.png'),fullPage:true});
  // Explicit authenticated replay request in page context; token is retained solely
  // in this callback variable, never returned/logged/saved. UI correctly disables replay.
  const replay=await p2.evaluate(async({base,agent,key,request_id,request_digest})=>{const sr=await fetch(base+'/api/gex/sessions',{method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify({agent_id:agent})});const s=await sr.json();const headers={Authorization:'Bearer '+s.session_token,'X-GEX-Agent-ID':agent,'Content-Type':'application/json'};const rr=await fetch(base+'/api/gex/requests/'+request_id+'/decision',{method:'POST',headers,body:JSON.stringify({request_digest,decision:'APPROVED',reason:'Independent explicit replay denial verification.'})});const body=await rr.json();await fetch(base+'/api/gex/sessions/current',{method:'DELETE',headers});return {status:rr.status,body};},{base,agent,key:cred.api_key,request_id:proposal.request_id,request_digest:proposal.request_digest});fs.writeFileSync(path.join(out,'replay-denial.json'),JSON.stringify(replay,null,2));if(replay.status!==409)throw Error('Replay was not denied');
  await p2.getByRole('button',{name:'Revocar y borrar sesión'}).click();await ctx2.close();
  for(const [f,h] of Object.entries(manifest))if(hash(f)!==h)throw Error('Candidate changed during verification: '+f);
  fs.writeFileSync(path.join(out,'live-result.json'),JSON.stringify({status:'PASS',request_id:proposal.request_id,provider:proposal.provider,identities,errors,provider_calls:1,restart_readback:true,replay_http:replay.status},null,2));console.log(JSON.stringify({status:'PASS',request_id:proposal.request_id,provider:proposal.provider}));
}catch(e){fs.writeFileSync(path.join(out,'live-result.json'),JSON.stringify({status:'FAIL',error:String(e.message),identities,errors},null,2));console.log('FAIL '+String(e.message));process.exitCode=1;}
finally{if(browser)await browser.close();await stop();fs.writeFileSync(path.join(out,'owned-processes.json'),JSON.stringify(identities,null,2));fs.closeSync(logfile);}
