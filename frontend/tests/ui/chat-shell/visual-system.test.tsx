// @vitest-environment jsdom
import {expect,it} from 'vitest'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
const css=readFileSync('src/VisualSystem.css','utf8'),ast=postcss.parse(css)
const allowed=new Set(['background','color','font-family','font-size','font-weight','border-color','border-top-color','border-left-color','border-radius','box-shadow','outline-color','padding-block','padding-inline'])
it('is a finite decoration layer with no layout, stacking, generated content, breakpoints or universal reset',()=>{
 ast.walkAtRules(rule=>{throw new Error('Unexpected at-rule '+rule.name)})
 ast.walkRules(rule=>{expect(rule.selector.startsWith('#root .app-shell')).toBe(true);expect(rule.selector).not.toContain('*')})
 ast.walkDecls(d=>{expect(d.important).not.toBe(true);expect(d.prop.startsWith('--vs-')||allowed.has(d.prop),d.prop).toBe(true);if(d.prop==='border-radius')expect(d.value).toBe('0')})
})
it('defines and actually consumes the three distinct surface tokens and common title/spacing/accent tokens',()=>{
 const definitions=new Map<string,string>(),uses=new Set<string>()
 ast.walkDecls(d=>{if(d.prop.startsWith('--vs-'))definitions.set(d.prop,d.value);else for(const match of d.value.matchAll(/var\((--vs-[a-z-]+)\)/g))uses.add(match[1])})
 expect(new Set(['--vs-base','--vs-work','--vs-raised'].map(key=>definitions.get(key))).size).toBe(3)
 for(const token of definitions.keys())expect(uses.has(token),token).toBe(true)
 for(const token of uses)expect(definitions.has(token),token).toBe(true)
 const gradientDefinitions:string[]=[];ast.walkDecls(d=>{if(d.value.includes('gradient('))gradientDefinitions.push(d.prop)})
 expect(gradientDefinitions).toEqual(['--vs-header'])
 const headers:string[]=[];ast.walkRules(rule=>{rule.walkDecls(d=>{if(d.value==='var(--vs-header)')headers.push(rule.selector)})})
 expect(headers).toHaveLength(1);expect(headers[0]).toContain('.data-layer-header');expect(headers[0]).not.toContain('.chat-inspection-counters')
})
it('loads the shared visual layer once immediately after ServiceSurfaces without freezing unrelated App evolution',()=>{
 const source=readFileSync('src/App.tsx','utf8')
 const imports=Array.from(source.matchAll(/^import ['"]([^'"\n]+\.css)['"]/gm),match=>match[1])
 expect(imports.filter(path=>path==='./VisualSystem.css')).toHaveLength(1)
 expect(imports.filter(path=>path==='./ServiceSurfaces.css')).toHaveLength(1)
 expect(imports.indexOf('./VisualSystem.css')).toBe(imports.indexOf('./ServiceSurfaces.css')+1)
 expect(source.split("import './VisualSystem.css'")).toHaveLength(2)
})

const consumers=[
 ['AgentChat','control-chat'],['Communications','communications'],['Contacts','contacts-page'],['WorkspaceManager','workspace-manager'],
 ['AgentManagement','agent-management'],['AgentBuilder','agent-builder'],['AgentTasks','agent-tasks'],['AgentRunner','agent-runner'],
 ['AgentEvaluationLab','evaluation-lab'],['CapabilityManager','capability-manager'],['ExternalConnections','external-connections'],
 ['JobHistory','job-history'],['ProviderSettings','provider-settings'],['CognitionSettings','cognition-settings'],['WhatsAppSettings','whatsapp-settings'],
 ['ModelAssignments','model-assignments'],['ChatInspection','chat-inspection'],['WindowPanel','window-panel']
]
it.each(consumers)('adapts a real existing component consumer: %s / %s',(file,consumer)=>{
 const source=readFileSync(`src/components/${file}.tsx`,'utf8')
 expect(source).toContain(consumer);expect(css).toContain('.'+consumer)
 expect(source).toMatch(/className=/)
})
it('adapts actual card/fieldset/list groups and main headers instead of fictional capability or workspace headings',()=>{
 for(const selector of ['.capability-card','.capability-proposal','.external-connections fieldset','.communications fieldset','.contacts-list > li','.agent-management article','.card .card'])expect(css).toContain(selector)
 expect(css).not.toContain('.capability-manager-header');expect(css).not.toContain('.workspace-heading')
 expect(readFileSync('src/components/WorkspaceManager.tsx','utf8')).toContain('<header><h2>')
 expect(readFileSync('src/components/CapabilityManager.tsx','utf8')).toContain('<ExternalConnections />')
 expect(readFileSync('src/components/ExternalConnections.tsx','utf8')).toContain('<header><h3')
 expect(readFileSync('src/components/AgentBuilder.tsx','utf8')).toContain('className="wizard-header"')
})
it('leaves semantic outcomes and role frames unpainted, keeps distinct author headers and finite rectangular ornaments',()=>{
 for(const token of ['integrity--checked','integrity--unverified','integrity--unavailable','status-available','.badge','.wm-review','.communications-error','.contacts-alert',"[role='alert']"])expect(css).not.toContain(token)
 const roleHeaders:Record<string,string>={}
 ast.walkRules(rule=>rule.walkDecls(d=>{if(rule.selector.endsWith('> .control-message-heading')&&d.prop==='background')roleHeaders[rule.selector]=d.value}))
 expect(Object.values(roleHeaders)).toEqual(['#16303b','#21344a'])
 expect(css).not.toMatch(/\.control-message(?:-user)?\s*\{/)
 for(const selector of ['.welcome-mark','.prompt-suggestions button','.contacts-card-heading > span'])expect(css).toContain(selector)
})
it('uses tokens for readable normal text with sufficient contrast against all three surfaces',()=>{
 const values:Record<string,string>={};ast.walkDecls(d=>{if(d.prop.startsWith('--vs-'))values[d.prop]=d.value})
 function luminance(hex:string){const c=hex.slice(1).match(/../g)!.map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722}
 for(const foreground of ['--vs-text','--vs-muted'])for(const background of ['--vs-base','--vs-work','--vs-raised'])expect((luminance(values[foreground])+.05)/(luminance(values[background])+.05)).toBeGreaterThanOrEqual(4.5)
})
