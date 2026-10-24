import {expect,it} from 'vitest'
import {readFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import postcss from 'postcss'
const paths=['src/components/AgentChat.css','src/App.css','src/components/ChatInspection.css']
const fixtureRoot=new URL('./fixtures/inspector-color/',import.meta.url)
const provenance=JSON.parse(readFileSync(new URL('PROVENANCE.json',fixtureRoot),'utf8')) as {files:Array<{fixture:string;sha256:string;bytes:number}>}
function assertNoGeneratedContent(value:string){postcss.parse(value).walkDecls(d=>expect(d.prop.toLowerCase()).not.toBe('content'))}
const allowed=new Set(['color','background','background-image','border-color','border-top-color','border-bottom-color','border-left-color','border-right-color','border-radius','box-shadow','outline-color'])
for(const path of paths)it(`preserves prior CSS bytes and limits rectangular color decoration to its owning surface: ${path}`,()=>{
 const css=readFileSync(path,'utf8'),name=path.slice(path.lastIndexOf('/')+1),baseline=readFileSync(new URL(name,fixtureRoot)),before=baseline.toString('utf8')
 const receipt=provenance.files.find(file=>file.fixture===name)!
 expect(baseline.length).toBe(receipt.bytes);expect(createHash('sha256').update(baseline).digest('hex')).toBe(receipt.sha256)
 expect(css.startsWith(before)).toBe(true)
 const delta=css.slice(before.length).split('/* PANEL_NARROW_REPAIR:')[0],ast=postcss.parse(delta)
 expect(delta).toContain('linear-gradient(')
 let count=0
 ast.walkDecls(d=>{expect(allowed.has(d.prop),d.prop).toBe(true);if(d.prop==='border-radius')expect(d.value).toBe('0');count++})
 expect(count).toBeGreaterThan(5)
 ast.walkRules(rule=>{for(const selector of rule.selectors){expect(selector.startsWith(path.includes('AgentChat')?'.control-chat .chat-agent-panel':path.includes('App.css')?'.data-layer':'.chat-inspection'),selector).toBe(true)}})
})
it('keeps integrity warning semantics distinct from the teal checked state and adds no generated instruction',()=>{
 const css=readFileSync('src/components/ChatInspection.css','utf8'),delta=css.split('/* COLOR_INSPECTOR:')[1]
 expect(delta).toContain('.chat-inspection-integrity--checked')
 expect(delta).not.toContain('.chat-inspection-integrity--unverified')
 expect(delta).not.toContain('.chat-inspection-integrity--unavailable')
 for(const path of paths){const extra=readFileSync(path,'utf8').split('/* COLOR_INSPECTOR:')[1];assertNoGeneratedContent('/* COLOR_INSPECTOR:'+extra)}
})

it('detects actual generated-content declarations without treating alignment properties or selectors as content',()=>{
 expect(()=>assertNoGeneratedContent('.heading { justify-content: space-between; } .window-panel-content:has(details[open]) { display: none; }')).not.toThrow()
 expect(()=>assertNoGeneratedContent('.heading::before { content: "label"; }')).toThrow()
 expect(()=>assertNoGeneratedContent('.heading::before { CONTENT: "label"; }')).toThrow()
})
