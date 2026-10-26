import {fireEvent, screen} from '@testing-library/react'

type TestAgent = {
  id: string
  config: {
    name: string
    provider_id?: string
    model_id?: string
    tools?: string[]
  }
}

export function withPersistedDelegation(parent: any, agent: TestAgent, childConversationId: string) {
  const parentRevision = parent.revision ?? 0
  const proposal = {
    proposal_id: 'delegation_0123456789abcdef0123456789abcdef',
    state: 'PASSED',
    parent_conversation_id: parent.id,
    parent_revision: parentRevision,
    agent_id: agent.id,
    agent_name: agent.config.name,
    agent_config_sha256: 'a'.repeat(64),
    provider_id: agent.config.provider_id ?? 'ollama-cloud',
    model_id: agent.config.model_id ?? 'fixture-model',
    assigned_tools: agent.config.tools ?? [],
    task: 'Synthetic delegated work retained in the parent conversation.',
    task_sha256: 'b'.repeat(64),
    proposal_sha256: 'c'.repeat(64),
    expires_at: Math.floor(Date.now() / 1000) + 1800,
    child_conversation_id: childConversationId,
    child_revision: 1,
    child_trace_id: 'trace-synthetic-child',
    receipt_id: 'receipt-synthetic-child',
    assistant_message: 'Synthetic delegated result.',
    tools_executed: false,
  }
  return {
    ...parent,
    messages: [...(Array.isArray(parent.messages) ? parent.messages : []), {
      id: 'message-persisted-delegation',
      role: 'assistant',
      content: 'Delegación sintética ya registrada para este fixture.',
      references: {agent_delegation: proposal},
    }],
  }
}

export async function openDelegatedChild(agentName: string) {
  const open = await screen.findByRole('button', {name: /Open child conversation|Abrir conversación hija/i})
  fireEvent.click(open)
  await screen.findByRole('region', {name: agentName})
}
