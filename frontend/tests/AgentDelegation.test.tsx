// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AgentDelegation, { type AgentDelegationProposal } from '../src/components/AgentDelegation'
import AgentChat from '../src/components/AgentChat'
import {conversationButton} from './helpers/conversation-library'
import { resetLocaleForTests, setLocale, t } from '../src/i18n'

const proposal: AgentDelegationProposal = {
  proposal_id: 'delegation_0123456789abcdef0123456789abcdef', state: 'PROPOSED',
  parent_conversation_id: 'parent-1', parent_revision: 4, agent_id: 'agent-saved-1', agent_name: 'Synthetic reviewer',
  agent_config_sha256: 'a'.repeat(64), provider_id: 'ollama-cloud', model_id: 'fixture-model', assigned_tools: ['document_inventory'],
  task: 'Inventory four synthetic fixture files and return counts.', task_sha256: 'b'.repeat(64), proposal_sha256: 'c'.repeat(64), expires_at: 1_900_000_000,
}
const jsonResponse = (data: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data })
const parent = { id: 'parent-1', owner_kind: 'assistant', owner_id: 'app-assistant', status: 'active', revision: 5, messages: [] }

beforeEach(() => { document.documentElement.lang = 'en'; resetLocaleForTests(); setLocale('en'); HTMLElement.prototype.scrollIntoView = () => {} })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('shows a saved proposal without executing it and requires a human confirmation before a no-grant turn', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = []
  let onUpdate = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (init?.method === 'POST') return jsonResponse({ agent_delegation: { ...proposal, state: 'PASSED', child_conversation_id: 'child-1', child_revision: 1, child_trace_id: 'trace-child-1', receipt_id: 'receipt-1', assistant_message: 'Four synthetic files inventoried.', tools_executed: false }, conversation: parent, child_conversation: { id: 'child-1', owner_kind: 'agent', owner_id: proposal.agent_id, messages: [] } })
    return jsonResponse({})
  }))
  render(<AgentDelegation proposal={proposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={onUpdate} />)
  expect(screen.getByText('Proposal only. No child turn has run.')).toBeTruthy()
  expect(calls).toHaveLength(0)
  fireEvent.click(screen.getByRole('checkbox', { name: /reviewed the agent/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Run task' }))
  await waitFor(() => expect(calls.filter(call => call.init?.method === 'POST')).toHaveLength(1))
  const body = JSON.parse(String(calls[0].init?.body))
  expect(body).toEqual({ parent_conversation_id: 'parent-1', parent_revision: 4, proposal_sha256: 'c'.repeat(64), confirm: true, scope: {
    allow_tools: false, root: null, allow_export: false, expected_output_directory: null, review_work_id: null, review_candidate_id: null,
    review_scope_sha256: null, contact_id: null, allow_draft: false,
  } })
  await screen.findByText('Four synthetic files inventoried.')
  expect(onUpdate).toHaveBeenCalledWith(parent)
  expect(screen.getByText('trace-child-1')).toBeTruthy()
  expect(screen.getByText('receipt-1')).toBeTruthy()
})

it('requires choosing a folder and explicit tool consent, and keeps export and draft independently off by default', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url.startsWith('/api/document-tools/folders')) return jsonResponse({ roots: [{ path: 'synthetic-root', name: 'Synthetic workspace' }], directories: [{ path: 'synthetic-root/input', name: 'input' }], path: 'synthetic-root/input', parent: 'synthetic-root', output_directory: 'synthetic-root/output' })
    if (init?.method === 'POST') return jsonResponse({ agent_delegation: { ...proposal, state: 'INCONCLUSIVE' }, conversation: parent, child_conversation: null })
    return jsonResponse({})
  }))
  render(<AgentDelegation proposal={proposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={() => {}} />)
  fireEvent.click(screen.getByRole('checkbox', { name: /Allow assigned tools/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Choose folder' }))
  await screen.findByText('Synthetic workspace')
  fireEvent.click(screen.getByRole('button', { name: 'Use this folder' }))
  fireEvent.click(screen.getByRole('checkbox', { name: /reviewed the agent/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Run task' }))
  await waitFor(() => expect(calls.some(call => call.init?.method === 'POST')).toBe(true))
  const body = JSON.parse(String(calls.find(call => call.init?.method === 'POST')!.init?.body))
  expect(body.scope.allow_tools).toBe(true)
  expect(body.scope.root).toBe('synthetic-root/input')
  expect(body.scope.allow_export).toBe(false)
  expect(body.scope.allow_draft).toBe(false)
})

it('does not execute a stale parent revision and refreshes terminal status without retrying', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { calls.push(url); return jsonResponse({ agent_delegation: { ...proposal, state: 'INCONCLUSIVE' } }) }))
  const { rerender } = render(<AgentDelegation proposal={proposal} parentConversationId="parent-1" parentRevision={9} onConversationUpdate={() => {}} />)
  expect(screen.getByRole('button', { name: 'Run task' }).hasAttribute('disabled')).toBe(true)
  expect(calls).toHaveLength(0)
  rerender(<AgentDelegation proposal={{ ...proposal, state: 'INCONCLUSIVE' }} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(calls[0]).toContain('/api/agent-delegations/delegation_')
  expect(calls[0]).toContain('parent_conversation_id=parent-1')
  expect(calls[0]).not.toContain('/execute')
})

it('rejects a response whose child belongs to a different saved agent', async () => {
  const onUpdate = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ agent_delegation: { ...proposal, state: 'PASSED', child_conversation_id: 'other-child' }, conversation: parent, child_conversation: { id: 'other-child', owner_kind: 'agent', owner_id: 'different-agent', messages: [] } })))
  render(<AgentDelegation proposal={proposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={onUpdate} />)
  fireEvent.click(screen.getByRole('checkbox', { name: /reviewed the agent/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Run task' }))
  await screen.findByText('Child conversation identity mismatch')
  expect(onUpdate).not.toHaveBeenCalled()
})

it('renders the same explicit proposal and no inherited grants in Spanish', () => {
  document.documentElement.lang = 'es'
  render(<AgentDelegation proposal={proposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={() => {}} />)
  expect(screen.getByText('Delegación a agente guardado')).toBeTruthy()
  expect(screen.getByText('Los permisos y el historial principales no se copian a la conversación delegada.')).toBeTruthy()
  expect(screen.getByText('Solo propuesta. Aún no se ha ejecutado ningún turno hijo.')).toBeTruthy()
})

it('does not report expiry for a live proposal while explicit confirmation is still unchecked', () => {
  const liveProposal = { ...proposal, expires_at: Math.floor(Date.now() / 1000) + 600 }
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { calls.push(url); return jsonResponse({}) }))
  render(<AgentDelegation proposal={liveProposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={() => {}} />)
  expect(screen.getByText('Proposal only. No child turn has run.')).toBeTruthy()
  expect(screen.queryByRole('status')).toBeNull()
  expect((screen.getByRole('checkbox', { name: /reviewed the agent/i }) as HTMLInputElement).checked).toBe(false)
  expect(calls).toHaveLength(0)
})

it.each([
  { language: 'en', locale: 'en', expiryLabel: 'This proposal has expired.', refreshLabel: 'Refresh status' },
  { language: 'es', locale: 'es', expiryLabel: 'La propuesta ha caducado.', refreshLabel: 'Actualizar estado' },
])('shows an expired proposal and allows only a status refresh ($language)', async ({ language, locale, expiryLabel, refreshLabel }) => {
  document.documentElement.lang = language
  setLocale(locale as 'en' | 'es')
  const expiredProposal = { ...proposal, expires_at: Math.floor(Date.now() / 1000) - 1 }
  const calls: Array<{ url: string; method?: string }> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method })
    return jsonResponse({ agent_delegation: { ...expiredProposal, state: 'EXPIRED' } })
  }))
  render(<AgentDelegation proposal={expiredProposal} parentConversationId="parent-1" parentRevision={4} onConversationUpdate={() => {}} />)
  expect(screen.getByRole('status').textContent).toBe(expiryLabel)
  expect((screen.getByRole('button', { name: refreshLabel }) as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: refreshLabel }))
  await waitFor(() => expect(calls).toHaveLength(1))
  expect(calls[0].method).toBeUndefined()
  expect(calls[0].url).toContain('parent_conversation_id=parent-1')
  expect(calls.some(call => call.url.includes('/execute'))).toBe(false)
})

it('renders only the latest persisted card per proposal and resets on conversation change', async () => {
  const savedProposal = { ...proposal, parent_revision: 5 }
  const runningProposal = { ...savedProposal, state: 'RUNNING' as const, child_conversation_id: 'child-a' }
  const finalProposal = { ...runningProposal, state: 'PASSED' as const, child_revision: 1, child_trace_id: 'trace-a', receipt_id: 'receipt-a', assistant_message: 'Final answer from saved reviewer.' }
  const secondProposal = { ...savedProposal, proposal_id: 'delegation_fedcba9876543210fedcba9876543210', agent_id: 'agent-saved-2', agent_name: 'Second saved reviewer', task: 'Review another synthetic set.', proposal_sha256: 'd'.repeat(64), state: 'RUNNING' as const, child_conversation_id: 'child-b' }
  const secondFinal = { ...secondProposal, state: 'FAILED' as const, error_code: 'SYNTHETIC_FAILURE', assistant_message: 'Second task failed with a recorded reason.' }
  const thirdProposal = { ...savedProposal, proposal_id: 'delegation_abcdef0123456789abcdef0123456789', agent_id: 'agent-saved-3', agent_name: 'Reviewer in next conversation', task: 'Check the next conversation.', proposal_sha256: 'e'.repeat(64), state: 'PROPOSED' as const }
  const summary = { id: 'parent-1', owner_kind: 'assistant', owner_id: 'app-assistant', title: 'Orchestrator fixture', status: 'active', updated_at: '2026-10-24', revision: 4 }
  const nextSummary = { ...summary, id: 'parent-2', title: 'Other orchestrator fixture', revision: 2 }
  const conversation = { ...summary, messages: [] }
  const persisted = { ...summary, revision: 7, messages: [
    { id: 'proposal-a', role: 'assistant', content: 'Delegation proposed.', references: { agent_delegation: savedProposal } },
    { id: 'running-a', role: 'assistant', content: 'Delegation is running.', references: { agent_delegation: runningProposal } },
    { id: 'final-a', role: 'assistant', content: 'Delegation returned.', references: { agent_delegation: finalProposal } },
    { id: 'proposal-b', role: 'assistant', content: 'Second delegation proposed.', references: { agent_delegation: secondProposal } },
    { id: 'final-b', role: 'assistant', content: 'Second delegation failed.', references: { agent_delegation: secondFinal } },
  ] }
  const nextConversation = { ...nextSummary, messages: [{ id: 'proposal-c', role: 'assistant', content: 'Next conversation proposal.', references: { agent_delegation: thirdProposal } }] }
  const calls: Array<{ url: string; method?: string }> = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method })
    if (url === '/api/agents/list') return jsonResponse({ agents: [] })
    if (url === '/api/providers/chat-models') return jsonResponse({ models: [{ provider_id: 'ollama-cloud', model_id: 'model-1', label: 'Ollama', display_name: 'Model 1', state: 'ready', orchestrator_enabled: true }] })
    if (url === '/api/providers/selection') return jsonResponse({ provider_id: 'ollama-cloud', model_id: 'model-1' })
    if (url.startsWith('/api/conversations?')) return jsonResponse({ conversations: [summary, nextSummary] })
    if (url === '/api/conversations/parent-1') return jsonResponse(conversation)
    if (url === '/api/conversations/parent-2') return jsonResponse(nextConversation)
    if (url.startsWith('/api/conversation-proposals')) return jsonResponse({ proposals: [] })
    if (url === '/api/chat/control') return jsonResponse({ operation: 'agent_delegation', agent_delegation: finalProposal, conversation: persisted })
    return jsonResponse({})
  }))
  render(<AgentChat onNavigate={() => {}} />)
  await screen.findByRole('region', { name: 'Orchestrator fixture' })
  const input = screen.getByRole('textbox', { name: t('commerce.message_the_assistant_or_selected_agent') })
  fireEvent.change(input, { target: { value: 'Please delegate the inventory task' } })
  fireEvent.submit(input.closest('form')!)
  await screen.findByText('Final answer from saved reviewer.')
  expect(screen.getAllByRole('region', { name: 'Saved agent delegation' })).toHaveLength(2)
  expect(screen.getByText('Second task failed with a recorded reason.')).toBeTruthy()
  expect(screen.getByText('Delegation proposed.')).toBeTruthy()
  fireEvent.click(screen.getByText(t('commerce.conversations_and_agents')))
  fireEvent.click(conversationButton(document, 'Other orchestrator fixture'))
  await screen.findByText('Reviewer in next conversation')
  expect(screen.getAllByRole('region', { name: 'Saved agent delegation' })).toHaveLength(1)
  expect(screen.queryByText('Final answer from saved reviewer.')).toBeNull()
  expect(calls.filter(call => call.url.includes('/api/agent-delegations/') && call.method === 'POST')).toHaveLength(0)
})
