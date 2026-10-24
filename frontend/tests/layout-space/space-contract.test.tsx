// @vitest-environment jsdom
import {afterEach,expect,it} from 'vitest'
import {readFileSync,readdirSync} from 'node:fs'
import {resolve} from 'node:path'
import postcss from 'postcss'
const src=resolve(process.cwd(),'src')
const read=(path:string)=>readFileSync(resolve(src,path),'utf8')
const paths=['index.css','App.css','components/Communications.css','components/Contacts.css','components/WorkspaceManager.css','components/AgentManagement.css','components/AgentBuilder.css','components/AgentTasks.css','components/WhatsAppSettings.css','components/KnowledgeIngest.css','components/OntologyReview.css','components/CatalogQuality.css','components/GovernedFixtureRunner.css','components/DirectoryScanRun.css','components/AgentChat.css','features/decision-inspector/integration/DecisionInspector.css','features/decision-inspector/shell/InspectorShell.css','features/ber-effect-inspector/BerEffectRecordInspector.css','ServiceSurfaces.css']
function install(){
 // jsdom has no container-query/layout engine. Strip conditional branches so
 // assertions concern only unconditional desktop style contracts, not pixels.
 const style=document.createElement('style')
 style.textContent=paths.map(path=>{const ast=postcss.parse(read(path));ast.walkAtRules(rule=>rule.remove());return ast.toString()}).join('\n')
 document.head.append(style)
 document.body.innerHTML='<div class="app-shell"><main class="app-view"></main></div>'
 return document.querySelector('main')!
}
afterEach(()=>{document.head.innerHTML='';document.body.innerHTML=''})
it('keeps compact mobile navigation scrollable and settings visible above the work area',()=>{
 const ast=postcss.parse(read('App.css')),mobile:Record<string,Record<string,string>>={}
 ast.walkAtRules('media',media=>{if(media.params!=='(max-width: 760px)')return
  media.walkRules(rule=>{mobile[rule.selector]??={};rule.walkDecls(decl=>{mobile[rule.selector][decl.prop]=decl.value})})
 })
 expect(mobile['.workspace-sidebar']['display']).toBe('grid')
 expect(mobile['.workspace-sidebar .workspace-sidebar-footer']['display']).toBe('flex')
 expect(mobile['.workspace-sidebar .primary-navigation']['overflow-x']).toBe('auto')
 expect(mobile['.workspace-sidebar .navigation-group']['flex-wrap']).toBe('nowrap')
 expect(mobile['.workspace-sidebar .workspace-sidebar-brand']['height']).toBe('36px')
})
it.each(['communications','contacts-page','workspace-manager','agent-management','agent-builder','agent-tasks','whatsapp-settings','knowledge-ingest','ontology-review','catalog-quality','governed-fixture','directory-scan-run'])('gives the %s work surface the available width without a page cap',className=>{
 const main=install(),panel=document.createElement('section');panel.className=className;main.append(panel)
 const style=getComputedStyle(panel)
 expect(style.maxWidth).toBe('none');expect(style.width).toBe('100%');expect(style.minWidth).toBe('0');expect(style.minHeight).toBe('0')
})
it('keeps inactive persisted panels hidden while visible editors can grow',()=>{
 const main=install();main.innerHTML='<section class="workspace-manager"><section role="tabpanel" hidden>Hidden state</section><section role="tabpanel"><label>Content<textarea></textarea></label></section></section>'
 const panels=main.querySelectorAll('section[role=tabpanel]')
 expect(getComputedStyle(panels[0]).display).toBe('none');expect(getComputedStyle(panels[1]).display).toBe('flex')
})
it('uses full dialog dimensions and intrinsic header rows instead of fixed header subtraction',()=>{
 for(const path of ['App.css','components/ChatTools.css']){
  const css=read(path);expect(css).not.toMatch(/(?:width|height):\s*min\((?:1180|820|960|720)px/)
 }
 const ast=postcss.parse(read('App.css'))
 const rules:string[]=[];ast.walkDecls('grid-template-rows',d=>{rules.push(d.value)})
 expect(rules).toContain('auto minmax(0, 1fr)')
 expect(read('App.css')).not.toMatch(/height:\s*calc\(100% - (?:58|56)px\)/)
})
it('removes large minimums from chat panel and keeps tables and write diffs scrollable',()=>{
 const chat=read('components/AgentChat.css'),services=read('ServiceSurfaces.css')
 expect(chat).not.toMatch(/min-height:\s*(?:280|360)px/)
 expect(chat).toContain('.chat-agent-panel-slot:has(.chat-agent-panel[open])')
 expect(chat).toContain('scrollbar-width: thin')
 expect(services).toMatch(/\.workspace-write-review pre\s*\{[^}]*white-space:\s*pre;[^}]*overflow:\s*auto/)
 expect(services).toContain("[role='tabpanel'][hidden] { display: none; }")
})
it('limits inner reading measure while interactive message wrappers fill available space',()=>{
 const main=install();main.innerHTML='<section class="control-chat"><article class="control-message control-message-assistant"><div class="assistant-markdown"><p>Text</p><table><tbody><tr><td>Evidence</td></tr></tbody></table></div></article></section>'
 expect(getComputedStyle(main.querySelector('article')!).maxWidth).toBe('none')
 expect(read('components/AgentChat.css')).toContain('max-inline-size: 76ch')
 expect(read('components/AssistantMarkdown.css')).toContain('overflow-x: auto')
})
it('keeps shared agent-list styles inside their owning component',()=>{
 for(const path of ['components/AgentBuilder.css','components/AgentRunner.css']){
  const ast=postcss.parse(read(path));ast.walkRules(rule=>{
   if(rule.selector.includes('.agents-list'))expect(rule.selector).toMatch(/\.(?:agent-builder|agent-runner) \.agents-list/)
  })
 }
})
it('parses every application CSS file and rejects accidentally emitted invalid auto maxima',()=>{
 function walk(folder:string){for(const file of readdirSync(folder,{withFileTypes:true})){
  const path=resolve(folder,file.name);if(file.isDirectory())walk(path);else if(file.name.endsWith('.css')){
   const ast=postcss.parse(readFileSync(path,'utf8'));ast.walkDecls(decl=>{
    if(decl.prop==='max-height'||decl.prop==='max-width')expect(decl.value).not.toBe('auto')
   })
  }
 }}walk(src)
})
