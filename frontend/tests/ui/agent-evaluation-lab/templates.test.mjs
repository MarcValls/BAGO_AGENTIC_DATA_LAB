import assert from 'node:assert/strict'
import { after, afterEach, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, Event: dom.window.Event, MouseEvent: dom.window.MouseEvent, getComputedStyle: dom.window.getComputedStyle, requestAnimationFrame: cb => setTimeout(cb, 0), cancelAnimationFrame: clearTimeout, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
const React = await import('react')
const { render, screen, fireEvent, cleanup } = await import('@testing-library/react')
const { default: Lab } = await server.ssrLoadModule('/src/components/AgentEvaluationLab.tsx')
const { setLocale } = await server.ssrLoadModule('/src/i18n/index.ts')
const originalFetch = globalThis.fetch
let requests = []
const response = body => ({ok: true, status: 200, json: async () => body})
globalThis.fetch = async (input, init) => {
  const url = String(input); requests.push({url, method: init?.method || 'GET', body: init?.body})
  if (url === '/api/agents/list') return response({agents:[{id:'agent_12345678',config:{name:'Test'}}]})
  if (url === '/api/providers/ollama/models') return response({models:[]})
  if (url === '/api/providers/ollama/status') return response({state:'unavailable'})
  if (url === '/api/evaluations/suites') return response({suites:[]})
  if (url.startsWith('/api/evaluations/runs')) return response({runs:[]})
  throw new Error('unexpected request '+url)
}
afterEach(() => { cleanup(); requests = [] })
after(async () => { globalThis.fetch = originalFetch; await server.close(); dom.window.close() })
it('ordered Spanish levels prepare editable drafts without saving or inference', async () => {
 setLocale('es'); render(React.createElement(Lab)); fireEvent.click(await screen.findByRole('button',{name:/Nueva batería/i}))
 const buttons = screen.getAllByRole('button').filter(b => /^(Verde|Azul|Ámbar|Rojo|Violeta) ·/.test(b.textContent.trim()))
 assert.deepEqual(buttons.map(b=>b.textContent.trim().split(' · ')[0]), ['Verde','Azul','Ámbar','Rojo','Violeta'])
 fireEvent.click(buttons[4]); assert.equal(screen.getByLabelText(/Nombre de la batería/i).value,'Violeta · Complejo')
 const prompts=screen.getAllByLabelText(/^Instrucción|^Prompt/i); assert.equal(prompts.length,2); fireEvent.change(prompts[0],{target:{value:'Cambiar borrador'}}); assert.equal(prompts[0].value,'Cambiar borrador')
 assert.equal(requests.filter(r=>r.method==='POST').length,0)
})
it('offers English levels when language is English', async () => {
 setLocale('en'); render(React.createElement(Lab)); fireEvent.click(await screen.findByRole('button',{name:/New suite/i})); assert.ok(screen.getByRole('button',{name:/Green · Introductory/i})); fireEvent.click(screen.getByRole('button',{name:/Purple · Complex/i})); assert.equal(screen.getByLabelText(/Suite name/i).value,'Purple · Complex'); assert.equal(requests.filter(r=>r.method==='POST').length,0)
})

it('protects edited drafts from replacement when cancelled', async () => {
 setLocale('en'); render(React.createElement(Lab)); fireEvent.click(await screen.findByRole('button',{name:/New suite/i}));
 fireEvent.click(screen.getByRole('button',{name:/Green .* Introductory/i}));
 const title=screen.getByLabelText(/Suite name/i); fireEvent.change(title,{target:{value:'My draft'}});
 let prompt=''; window.confirm=(message)=>{prompt=message;return false};
 fireEvent.click(screen.getByRole('button',{name:/Blue .* Basic/i}));
 assert.equal(title.value,'My draft'); assert.match(prompt,/Replace/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
})
