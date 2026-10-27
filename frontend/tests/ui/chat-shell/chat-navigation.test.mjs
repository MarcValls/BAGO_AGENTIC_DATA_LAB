import assert from 'node:assert/strict'
import { after, afterEach, beforeEach, it } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node,
  Event: dom.window.Event,
  MouseEvent: dom.window.MouseEvent,
  getComputedStyle: dom.window.getComputedStyle,
  requestAnimationFrame: (callback) => setTimeout(callback, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  IS_REACT_ACT_ENVIRONMENT: true,
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
dom.window.HTMLElement.prototype.scrollIntoView = () => {}

const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
const React = await import('react')
const { cleanup, fireEvent, render, screen, within } = await import('@testing-library/react')
const {setLocale,resetLocaleForTests}=await server.ssrLoadModule('/src/i18n/index.ts')
beforeEach(()=>{resetLocaleForTests();setLocale('en')})
const { default: AgentChat } = await server.ssrLoadModule('/src/components/AgentChat.tsx')

const agent = {
  id: 'agent_support',
  config: { name: 'Support agent', type: 'tool', model_id: 'gemma4:31b', description: 'Answers support questions.' },
}

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

const fetchRestorers = []
function stubFetch(fetcher) {
  const original = globalThis.fetch
  globalThis.fetch = fetcher
  fetchRestorers.push(() => { globalThis.fetch = original })
}

afterEach(() => {
  cleanup()
  for (const restore of fetchRestorers.splice(0)) restore()
})
after(async () => { await server.close(); dom.window.close() })

it('shows linked-agent navigation and the selected project policy, separate from public-web consent', async () => {
  const conversationRequests = []
  stubFetch(async (input) => {
    const url = String(input)
    if (url === '/api/providers/chat-models') return response({ detail: 'Provider unavailable in this synthetic fixture' }, 503)
    if (url === '/api/providers/selection') return response({ provider_id: null, model_id: null })
    if (url === '/api/agents/list') return response({ agents: [agent] })
    if (url === '/api/project-folders/v1/active') return response({ project_id: 'project-1', title: 'Selected project', scope: 'project', root: 'D:/projects/selected-project' })
    if (url === '/api/project-permissions') return response({
      project_id: 'project-1', root: 'D:/projects/selected-project',
      binding: { workspace_root: 'D:/projects/selected-project', revision: 8 },
      revision: 3, state: 'active', read_directories: ['src'], write_directories: ['docs'],
    })
    if (url === '/api/project-permissions/directories') return response({
      project_id: 'project-1', root: 'D:/projects/selected-project',
      binding: { workspace_root: 'D:/projects/selected-project', revision: 8 },
      revision: 3, directory: '.', directories: [{ name: 'src', path: 'src' }, { name: 'docs', path: 'docs' }], truncated: false,
    })
    if (url.startsWith('/api/conversations?')) {
      conversationRequests.push(url)
      return response({ conversations: [] })
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  const chatTarget = document.createElement('main')
  document.body.append(chatTarget)
  let providerSettingsOpened = false
  let manageAgentsOpened = false
  render(React.createElement(AgentChat, {
    cognitiveMode: 'baseline',
    onOpenCognitionSettings: () => {},
    onNavigate: () => {},
    onOpenProviderSettings: () => { providerSettingsOpened = true },
    onManageAgents: () => { manageAgentsOpened = true },
  }), { container: chatTarget })

  const panel = chatTarget.querySelector('.chat-agent-panel')
  assert.ok(panel)
  assert.equal(panel.open, false)
  fireEvent.click(panel.querySelector('summary'))
  assert.equal(panel.open, true)
  const agentNavigation = chatTarget.querySelector('.control-chat-sidebar')
  assert.ok(agentNavigation)
  assert.equal(chatTarget.querySelector('.chat-agent-panel-slot').contains(agentNavigation), true)
  assert.equal(chatTarget.querySelector('.control-chat-main') !== null, true)
  assert.match(agentNavigation.textContent, /Agents in this chat/)
  assert.match(agentNavigation.textContent, /No agent has been used in this conversation yet/)
  assert.equal(agentNavigation.textContent.includes('Support agent'), false)
  fireEvent.click(screen.getByRole('button', { name: 'Manage agents' }))
  assert.equal(manageAgentsOpened, true)
  await screen.findByRole('button', { name: 'BAGO5 orchestrator' })

  const projectPanel = await screen.findByRole('region', { name: 'Contexto del proyecto' })
  const permissions = within(projectPanel).getByRole('region', { name: 'Permisos del proyecto' })
  assert.equal((await within(permissions).findByText('D:/projects/selected-project')).textContent, 'D:/projects/selected-project')
  await screen.findByText('src')
  await screen.findByText('docs')
  assert.match(permissions.querySelector('dl')?.textContent ?? '', /Lectura\s*src/)
  assert.match(permissions.querySelector('dl')?.textContent ?? '', /Escritura\s*docs/)
  assert.equal(screen.queryByRole('checkbox', { name: 'Allow project file reads' }), null)
  assert.equal(screen.queryByLabelText('Project-relative paths'), null)
  assert.ok(screen.getByRole('checkbox', { name: 'Allow public web reading' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Open provider settings' }))
  assert.equal(providerSettingsOpened, true)
  assert.ok(conversationRequests.length > 0)
  assert.ok(conversationRequests.every((url) => new URLSearchParams(url.split('?')[1]).get('owner_kind') === 'assistant'))
})
