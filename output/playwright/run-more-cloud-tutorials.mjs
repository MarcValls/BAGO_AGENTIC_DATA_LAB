import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
const pw = 'C:/Users/AMTEC_Terminal_1º/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright/index.mjs'
const { chromium } = await import(pathToFileURL(pw).href)
const root = process.cwd()
const base = path.join(root,'output','playwright')
const slugs = ['tutorial-peluquerias','tutorial-kebap']
const configs = slugs.map(slug=>({folder:path.join(base,slug),config:JSON.parse(fs.readFileSync(path.join(base,slug,'demo.json'),'utf8'))}))
const browser=await chromium.launch({headless:true})
const context=await browser.newContext({viewport:{width:1600,height:900}})
const page=await context.newPage()
page.setDefaultTimeout(20000)
await page.goto('http://127.0.0.1:8081',{waitUntil:'domcontentloaded'})

const allProfiles=configs.flatMap(({config})=>[
  {...config.extractor,type:'rag'},
  {...config.reviewer,type:'rag'},
])
let profiles=(await (await page.request.get('http://127.0.0.1:8081/api/agents/list')).json()).agents
let uiCreated=false
await page.getByRole('button',{name:/Agent Builder/i}).click()
await page.waitForSelector('.agent-builder')
for(const p of allProfiles){
  let found=profiles.find(a=>a.config.name===p.name)
  if(found) continue
  if(uiCreated) {
    await page.getByRole('button',{name:/Create Another Agent/i}).click()
    await page.getByRole('button',{name:/Create Custom Agent/i}).click()
  } else await page.getByRole('button',{name:/Create Custom Agent/i}).click()
  await page.waitForSelector('.agent-builder .form-group')
  const groups=page.locator('.agent-builder .form-group')
  await groups.nth(0).locator('input').fill(p.name)
  await groups.nth(1).locator('textarea').fill(p.description)
  await groups.nth(3).locator('textarea').fill(p.system_prompt)
  const safe= p.name.toLowerCase().includes('corte')?'tutorial-peluquerias':'tutorial-kebap'
  const shot=path.join(base,safe,'cloud-runs')
  fs.mkdirSync(shot,{recursive:true})
  await page.screenshot({path:path.join(shot,'builder-'+(p.name.includes('Extractor')?'extractor':'reviewer')+'.png')})
  await page.getByRole('button',{name:/Preview/i}).click()
  await page.getByRole('button',{name:/Save Agent/i}).click()
  await page.getByText('Agent saved successfully!',{exact:false}).waitFor({timeout:20000})
  await page.getByRole('button',{name:/Create Another Agent/i}).waitFor({timeout:20000})
  profiles=(await (await page.request.get('http://127.0.0.1:8081/api/agents/list')).json()).agents
  found=profiles.find(a=>a.config.name===p.name)
  if(!found) throw new Error('Saved agent not returned by API: '+p.name)
  uiCreated=true
}

for(const {folder,config} of configs){
  const out=path.join(folder,'cloud-runs')
  fs.mkdirSync(out,{recursive:true})
  const saved=(await (await page.request.get('http://127.0.0.1:8081/api/agents/list')).json()).agents
  const groupProfiles=[config.extractor,config.reviewer].map(p=>saved.find(a=>a.config.name===p.name))
  if(groupProfiles.some(p=>!p)) throw new Error('Missing expected profile for '+config.business)
  fs.writeFileSync(path.join(out,'profiles.json'),JSON.stringify(groupProfiles,null,2),'utf8')
  await page.getByRole('button',{name:'Chat',exact:true}).click()
  const summary=page.locator('summary').filter({hasText:'Workspace and agents'})
  if(await summary.count()){
    const details=page.locator('details').filter({has:summary})
    if(!(await details.evaluate(el=>el.open))) await summary.click()
  }
  for(let i=0;i<2;i++){
    const runPath=path.join(out,'run-'+(i+1)+'.json')
    if(fs.existsSync(runPath)) continue
    const profile=groupProfiles[i]
    await page.getByRole('button',{name:new RegExp(profile.config.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}).click()
    const newButton=page.getByRole('button',{name:'New',exact:true})
    if(await newButton.count()) await newButton.click()
    await page.getByRole('checkbox',{name:/Authorize exact project files for this message/i}).check()
    const filePaths=i===0
      ? [path.relative(root,path.join(folder,'inputs',config.inputs)).replaceAll('\\','/')]
      : ['inputs/'+path.basename(config.inputs),'inputs/policy.md','inputs/qa-expected.md'].map(p=>path.relative(root,path.join(folder,p)).replaceAll('\\','/'))
    await page.locator('.workspace-read-paths textarea').fill(filePaths.join('\n'))
    await page.locator('#control-chat-input').fill(config.messages[i])
    const promise=page.waitForResponse(r=>r.url().includes('/api/agents/')&&r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:180000})
    await page.getByRole('button',{name:'Send'}).click()
    const response=await promise
    const body=await response.json()
    if(!response.ok()||body.source!=='ollama') throw new Error('Cloud chat failed for '+profile.config.name+': '+JSON.stringify(body))
    fs.writeFileSync(runPath,JSON.stringify(body,null,2),'utf8')
    await page.waitForTimeout(250)
    await page.screenshot({path:path.join(out,'result-'+(i+1)+'.png'),fullPage:true})
  }
}
await browser.close()
console.log(JSON.stringify({profiles:allProfiles.map(p=>p.name),runFiles:configs.map(({folder})=>[path.join(folder,'cloud-runs','run-1.json'),path.join(folder,'cloud-runs','run-2.json')])},null,2))
