import { pathToFileURL } from 'node:url'
import fs from 'node:fs/promises'
const { chromium } = await import(pathToFileURL('C:/Users/AMTEC_Terminal_1º/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright/index.mjs').href)
const out='output/playwright/tutorial-otras-pantallas'
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:900}, deviceScaleFactor:1})
const errors=[]; page.on('pageerror',e=>errors.push(String(e)))
await page.goto('http://127.0.0.1:8081/',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(1600)
const manifest=[]
const snap=async(name,action)=>{await action(); await page.waitForTimeout(450);const body=await page.locator('body').innerText();await page.screenshot({path:`${out}/${name}.png`});manifest.push({name,body:body.slice(0,6500),title:await page.locator('#data-layer-title').textContent().catch(()=>null)});}
await snap('01-chat',async()=>{})
for (const [slug,label] of [['02-summary','Summary'],['03-retrieval','Retrieval & Ontology'],['04-authorization','Authorization'],['05-trace','Trace'],['06-evaluation','Evaluation'],['07-inspector','Decision Inspector'],['08-jobs','Job History']]) {
 await page.getByRole('button',{name:'Open Inspect'}).click();
 await page.getByRole('button',{name:label,exact:true}).click();
 await page.waitForTimeout(350);
 await page.screenshot({path:`${out}/${slug}.png`});
 const body=await page.locator('#data-layer').innerText();manifest.push({name:slug,body,title:await page.locator('#data-layer-title').textContent()});
 await page.keyboard.press('Escape'); await page.waitForTimeout(200);
}
for (const [slug,label] of [['09-capabilities','Capabilities'],['10-runner','Agent Runner']]) {await page.getByRole('button',{name:label,exact:true}).click(); await page.waitForTimeout(500);await page.screenshot({path:`${out}/${slug}.png`});manifest.push({name:slug,body:(await page.locator('body').innerText()).slice(0,6500)});}
await fs.writeFile(`${out}/screen-capture-report.json`,JSON.stringify({url:page.url(),captured_at:new Date().toISOString(),page_errors:errors,screens:manifest},null,2))
console.log(JSON.stringify({page_errors:errors,screens:manifest.map(x=>({name:x.name,title:x.title,preview:x.body.slice(0,180)}))},null,2));await browser.close()
