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

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const React = await import('react')
const { cleanup, fireEvent, render, screen, waitFor } = await import('@testing-library/react')
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

it('mounts agent and conversation navigation in its panel and preserves authorization controls', async () => {
  const conversationRequests = []
  stubFetch(async (input) => {
    const url = String(input)
    if (url === '/api/providers/chat-models') return response({ detail: 'Provider unavailable in this synthetic fixture' }, 503)
    if (url === '/api/providers/selection') return response({ provider_id: null, model_id: null })
    if (url === '/api/agents/list') return response({ agents: [agent] })
    if (url.startsWith('/api/conversations?')) {
      conversationRequests.push(url)
      return response({ conversations: [] })
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  const chatTarget = document.createElement('main')
  document.body.append(chatTarget)
  let providerSettingsOpened = false
  render(React.createElement(AgentChat, {
    cognitiveMode: 'baseline',
    onOpenCognitionSettings: () => {},
    onNavigate: () => {},
    onOpenProviderSettings: () => { providerSettingsOpened = true },
  }), { container: chatTarget })

  const panel = chatTarget.querySelector('.chat-agent-panel')
  assert.ok(panel)
  assert.equal(panel.open, false)
  fireEvent.click(panel.querySelector('summary'))
  assert.equal(panel.open, true)
  const agentNavigation = await screen.findByRole('complementary', { name: 'Orchestrator conversations and agents' })
  assert.equal(chatTarget.querySelector('.chat-agent-panel-slot').contains(agentNavigation), true)
  assert.equal(chatTarget.querySelector('.control-chat-main') !== null, true)
  await screen.findByRole('button', { name: /Support agent/ })

  const authorizeReads = screen.getByRole('checkbox', { name: 'Allow project file reads' })
  assert.equal(authorizeReads.checked, false)
  assert.equal(screen.queryByLabelText('Project-relative paths'), null)
  fireEvent.click(authorizeReads)
  assert.ok(screen.getByLabelText('Project-relative paths'))
  fireEvent.click(authorizeReads)
  assert.equal(screen.queryByLabelText('Project-relative paths'), null)
  fireEvent.click(await screen.findByRole('button', { name: 'Open provider settings' }))
  assert.equal(providerSettingsOpened, true)

  fireEvent.click(screen.getByRole('button', { name: /Support agent/ }))
  await waitFor(() => assert.ok(screen.getByRole('heading', { name: 'Chat with Support agent' })))

  fireEvent.click(screen.getByRole('button', { name: 'Archived' }))
  await waitFor(() => assert.ok(conversationRequests.some((url) => url.includes('status=archived'))))

})
