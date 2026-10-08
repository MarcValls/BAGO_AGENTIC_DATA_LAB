import { useState, useEffect, useRef } from 'react'
import './AgentChat.css'

interface Agent {
  id: string
  config: {
    name: string
    description: string
    type: string
    system_prompt: string
    tools: string[]
  }
  created_at: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ChatSession {
  agent_id: string
  messages: Message[]
  created_at: string
}

export default function AgentChat() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchAgents()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/agents/list')
      const data = await response.json()
      setAgents(data.agents || [])
    } catch (error) {
      console.error('Error fetching agents:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const selectAgent = (agent: Agent) => {
    setSelectedAgent(agent)
    setMessages([
      {
        id: 'init_0',
        role: 'assistant',
        content: `Hi! I'm ${agent.config.name}. ${agent.config.description}`,
        timestamp: new Date().toISOString(),
      },
    ])
  }

  const sendMessage = async () => {
    if (!input.trim() || !selectedAgent) return

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsSending(true)

    try {
      const ws = new WebSocket('ws://localhost:8080/ws/agents/chat')

      ws.onopen = () => {
        ws.send(JSON.stringify({
          agent_id: selectedAgent.id,
          config: selectedAgent.config,
          message: input,
          conversation_history: messages,
        }))
      }

      let assistantResponse = ''
      const assistantId = `msg_${Date.now()}_response`

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'chunk') {
          assistantResponse += msg.data
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last?.id === assistantId) {
              return [...prev.slice(0, -1), { ...last, content: assistantResponse }]
            }
            return [
              ...prev,
              {
                id: assistantId,
                role: 'assistant',
                content: assistantResponse,
                timestamp: new Date().toISOString(),
              },
            ]
          })
        } else if (msg.type === 'done') {
          setIsSending(false)
          ws.close()
        } else if (msg.type === 'error') {
          setMessages((prev) => [
            ...prev,
            {
              id: `msg_error_${Date.now()}`,
              role: 'assistant',
              content: `Error: ${msg.data}`,
              timestamp: new Date().toISOString(),
            },
          ])
          setIsSending(false)
          ws.close()
        }
      }

      ws.onerror = () => {
        setMessages((prev) => [
          ...prev,
          {
            id: `msg_error_${Date.now()}`,
            role: 'assistant',
            content: 'Connection error. Try again.',
            timestamp: new Date().toISOString(),
          },
        ])
        setIsSending(false)
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg_error_${Date.now()}`,
          role: 'assistant',
          content: `Error: ${error}`,
          timestamp: new Date().toISOString(),
        },
      ])
      setIsSending(false)
    }
  }

  const exportChat = () => {
    if (!selectedAgent || messages.length === 0) return

    const content = messages
      .map((m) => `${m.role.toUpperCase()}: ${m.content}`)
      .join('\n\n')

    const header = `Chat with ${selectedAgent.config.name}\nStarted: ${new Date().toLocaleString()}\n\n`
    const fullContent = header + content

    const blob = new Blob([fullContent], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chat-${selectedAgent.id}-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const clearChat = () => {
    if (selectedAgent) {
      setMessages([
        {
          id: 'init_0',
          role: 'assistant',
          content: `Hi! I'm ${selectedAgent.config.name}. ${selectedAgent.config.description}`,
          timestamp: new Date().toISOString(),
        },
      ])
    }
  }

  return (
    <div className="agent-chat">
      <div className="chat-sidebar">
        <h3>Available Agents</h3>
        <div className="agents-list">
          {agents.length === 0 ? (
            <p style={{ color: 'rgba(255, 255, 255, 0.5)' }}>No agents yet. Create one in Agent Builder.</p>
          ) : (
            agents.map((agent) => (
              <div
                key={agent.id}
                className={`agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`}
                onClick={() => selectAgent(agent)}
              >
                <div className="agent-name">{agent.config.name}</div>
                <div className="agent-type">{agent.config.type}</div>
                <div className="agent-desc">{agent.config.description}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="chat-main">
        {!selectedAgent ? (
          <div className="chat-empty">
            <div className="empty-icon">💬</div>
            <h2>Select an agent to start chatting</h2>
            <p>Choose an agent from the list on the left to begin a conversation</p>
          </div>
        ) : (
          <>
            <div className="chat-header">
              <div>
                <h2>{selectedAgent.config.name}</h2>
                <p>{selectedAgent.config.description}</p>
              </div>
              <div className="chat-actions">
                <button onClick={exportChat} className="btn btn-small" disabled={messages.length === 0}>
                  📥 Export
                </button>
                <button onClick={clearChat} className="btn btn-small btn-secondary">
                  🗑️ Clear
                </button>
              </div>
            </div>

            <div className="chat-messages">
              {messages.map((msg, idx) => (
                <div key={msg.id} className={`message message-${msg.role}`}>
                  <div className="message-role">{msg.role === 'user' ? '👤 You' : '🤖 Agent'}</div>
                  <div className="message-content">{msg.content}</div>
                  <div className="message-time">{new Date(msg.timestamp).toLocaleTimeString()}</div>
                </div>
              ))}
              {isSending && (
                <div className="message message-assistant">
                  <div className="message-role">🤖 Agent</div>
                  <div className="message-content typing">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !isSending) sendMessage()
                }}
                placeholder="Type a message..."
                disabled={isSending}
                className="chat-input"
              />
              <button
                onClick={sendMessage}
                disabled={isSending || !input.trim()}
                className={`btn btn-primary ${isSending ? 'disabled' : ''}`}
              >
                {isSending ? '⏳' : '📤'} Send
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
