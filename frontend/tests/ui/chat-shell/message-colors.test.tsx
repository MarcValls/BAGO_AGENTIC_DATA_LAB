import {expect,it} from 'vitest'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
const sheet=postcss.parse(readFileSync('src/components/ChatMessage.css','utf8'))
const declarations=(selector:string)=>{const out:Record<string,string>={};sheet.walkRules(rule=>{if(rule.selector===selector)rule.walkDecls(d=>{out[d.prop]=d.value})});return out}
it('keeps every message, internal frame, action and contextual menu corner square',()=>{
 const radii:string[]=[];sheet.walkDecls('border-radius',declaration=>{radii.push(declaration.value)})
 expect(radii.length).toBeGreaterThanOrEqual(6)
 expect(radii.every(value=>value==='0')).toBe(true)
 for(const selector of ['.control-chat .control-message','.control-chat .control-message > .control-message-heading','.control-chat .control-message .message-action','.chat-message-context-menu','.chat-message-context-menu > button'])expect(declarations(selector)['border-radius']).toBe('0')
})
it('uses contained gradient separator lines and distinct role borders without losing spatial hierarchy',()=>{
 const assistant=declarations('.control-chat .control-message'),user=declarations('.control-chat .control-message-user')
 expect(assistant['border-inline-start-width']).toBe('4px');expect(user['border-inline-end-width']).toBe('4px')
 expect(assistant['border-inline-start-color']).not.toBe(user['border-inline-end-color'])
 expect(user['margin-inline-start']).toBe('auto')
 expect(declarations('.control-chat .control-message > .control-message-heading').background).toContain('bottom / 100% 1px no-repeat')
 expect(declarations('.control-chat .control-message-user > .control-message-heading').background).toContain('linear-gradient')
 expect(declarations('.control-chat .control-message').overflow).toBeUndefined()
})
it('retains visible outlines, bounded context menu and quiet static decoration',()=>{
 expect(declarations('.control-chat .control-message:focus-visible').outline).toContain('2px solid')
 expect(declarations('.control-chat .control-message .message-action:focus-visible').outline).toContain('2px solid')
 expect(declarations('.chat-message-context-menu')['max-width']).toBe('calc(100vw - 16px)')
 expect(declarations('.chat-message-context-menu')['max-height']).toBe('calc(100dvh - 16px)')
 const animations:string[]=[];sheet.walkDecls(declaration=>{if(declaration.prop.startsWith('animation'))animations.push(declaration.value)})
 expect(animations).toEqual([])
})
