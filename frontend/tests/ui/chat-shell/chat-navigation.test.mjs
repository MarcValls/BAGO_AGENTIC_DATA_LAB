import assert from 'node:assert/strict'
import { after, afterEach, it } from 'node:test'
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

it('mounts agent and conversation navigation in the shell target and preserves its controls', async () => {
  const conversationRequests = []
  stubFetch(async (input) => {
    const url = String(input)
    if (url === '/api/agents/list') return response({ agents: [agent] })
    if (url.startsWith('/api/conversations?')) {
      conversationRequests.push(url)
      return response({ conversations: [] })
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  const sidebarTarget = document.createElement('aside')
  document.body.append(sidebarTarget)
  const chatTarget = document.createElement('main')
  document.body.append(chatTarget)
  let providerSettingsOpened = false
  render(React.createElement(AgentChat, {
    sidebarTarget,
    onNavigate: () => {},
    onOpenProviderSettings: () => { providerSettingsOpened = true },
  }), { container: chatTarget })

  const agentNavigation = await screen.findByRole('complementary', { name: 'Agent inventory' })
  assert.equal(sidebarTarget.contains(agentNavigation), true)
  assert.equal(chatTarget.querySelector('.control-chat-main') !== null, true)
  await screen.findByRole('button', { name: /Support agent/ })

  const composerInfo = chatTarget.querySelector('.chat-composer-info')
  assert.equal(composerInfo.open, false)
  assert.equal(composerInfo.querySelector('p').textContent, 'Authorized files are read-only and bounded. The exact excerpt and decision are recorded with SHA-256 receipts. This chat cannot write files or run jobs.')
  fireEvent.click(screen.getByText('About file access and privacy'))
  assert.equal(composerInfo.open, true)

  fireEvent.click(screen.getByRole('button', { name: /Support agent/ }))
  await waitFor(() => assert.ok(screen.getByRole('heading', { name: 'Support agent' })))

  fireEvent.click(screen.getByRole('button', { name: 'Archived' }))
  await waitFor(() => assert.ok(conversationRequests.some((url) => url.includes('status=archived'))))

  fireEvent.click(await screen.findByRole('button', { name: 'Configure Ollama provider' }))
  assert.equal(providerSettingsOpened, true)
})
