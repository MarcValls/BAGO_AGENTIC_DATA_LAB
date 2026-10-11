import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useRef } from 'react';
import './AgentChat.css';
export default function AgentChat() {
    const [agents, setAgents] = useState([]);
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const messagesEndRef = useRef(null);
    useEffect(() => {
        fetchAgents();
    }, []);
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);
    const fetchAgents = async () => {
        try {
            const response = await fetch('/api/agents/list');
            const data = await response.json();
            setAgents(data.agents || []);
        }
        catch (error) {
            console.error('Error fetching agents:', error);
        }
        finally {
            setIsLoading(false);
        }
    };
    const selectAgent = (agent) => {
        setSelectedAgent(agent);
        setMessages([
            {
                id: 'init_0',
                role: 'assistant',
                content: `Hi! I'm ${agent.config.name}. ${agent.config.description}`,
                timestamp: new Date().toISOString(),
            },
        ]);
    };
    const sendMessage = async () => {
        if (!input.trim() || !selectedAgent)
            return;
        const userMessage = {
            id: `msg_${Date.now()}`,
            role: 'user',
            content: input,
            timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsSending(true);
        try {
            const ws = new WebSocket('ws://localhost:8080/ws/agents/chat');
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    agent_id: selectedAgent.id,
                    config: selectedAgent.config,
                    message: input,
                    conversation_history: messages,
                }));
            };
            let assistantResponse = '';
            const assistantId = `msg_${Date.now()}_response`;
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'chunk') {
                    assistantResponse += msg.data;
                    setMessages((prev) => {
                        const last = prev[prev.length - 1];
                        if (last?.id === assistantId) {
                            return [...prev.slice(0, -1), { ...last, content: assistantResponse }];
                        }
                        return [
                            ...prev,
                            {
                                id: assistantId,
                                role: 'assistant',
                                content: assistantResponse,
                                timestamp: new Date().toISOString(),
                            },
                        ];
                    });
                }
                else if (msg.type === 'done') {
                    setIsSending(false);
                    ws.close();
                }
                else if (msg.type === 'error') {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: `msg_error_${Date.now()}`,
                            role: 'assistant',
                            content: `Error: ${msg.data}`,
                            timestamp: new Date().toISOString(),
                        },
                    ]);
                    setIsSending(false);
                    ws.close();
                }
            };
            ws.onerror = () => {
                setMessages((prev) => [
                    ...prev,
                    {
                        id: `msg_error_${Date.now()}`,
                        role: 'assistant',
                        content: 'Connection error. Try again.',
                        timestamp: new Date().toISOString(),
                    },
                ]);
                setIsSending(false);
            };
        }
        catch (error) {
            setMessages((prev) => [
                ...prev,
                {
                    id: `msg_error_${Date.now()}`,
                    role: 'assistant',
                    content: `Error: ${error}`,
                    timestamp: new Date().toISOString(),
                },
            ]);
            setIsSending(false);
        }
    };
    const exportChat = () => {
        if (!selectedAgent || messages.length === 0)
            return;
        const content = messages
            .map((m) => `${m.role.toUpperCase()}: ${m.content}`)
            .join('\n\n');
        const header = `Chat with ${selectedAgent.config.name}\nStarted: ${new Date().toLocaleString()}\n\n`;
        const fullContent = header + content;
        const blob = new Blob([fullContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-${selectedAgent.id}-${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };
    const clearChat = () => {
        if (selectedAgent) {
            setMessages([
                {
                    id: 'init_0',
                    role: 'assistant',
                    content: `Hi! I'm ${selectedAgent.config.name}. ${selectedAgent.config.description}`,
                    timestamp: new Date().toISOString(),
                },
            ]);
        }
    };
    return (_jsxs("div", { className: "agent-chat", children: [_jsxs("div", { className: "chat-sidebar", children: [_jsx("h3", { children: "Available Agents" }), _jsx("div", { className: "agents-list", children: agents.length === 0 ? (_jsx("p", { style: { color: 'rgba(255, 255, 255, 0.5)' }, children: "No agents yet. Create one in Agent Builder." })) : (agents.map((agent) => (_jsxs("div", { className: `agent-option ${selectedAgent?.id === agent.id ? 'selected' : ''}`, onClick: () => selectAgent(agent), children: [_jsx("div", { className: "agent-name", children: agent.config.name }), _jsx("div", { className: "agent-type", children: agent.config.type }), _jsx("div", { className: "agent-desc", children: agent.config.description })] }, agent.id)))) })] }), _jsx("div", { className: "chat-main", children: !selectedAgent ? (_jsxs("div", { className: "chat-empty", children: [_jsx("div", { className: "empty-icon", children: "\uD83D\uDCAC" }), _jsx("h2", { children: "Select an agent to start chatting" }), _jsx("p", { children: "Choose an agent from the list on the left to begin a conversation" })] })) : (_jsxs(_Fragment, { children: [_jsxs("div", { className: "chat-header", children: [_jsxs("div", { children: [_jsx("h2", { children: selectedAgent.config.name }), _jsx("p", { children: selectedAgent.config.description })] }), _jsxs("div", { className: "chat-actions", children: [_jsx("button", { onClick: exportChat, className: "btn btn-small", disabled: messages.length === 0, children: "\uD83D\uDCE5 Export" }), _jsx("button", { onClick: clearChat, className: "btn btn-small btn-secondary", children: "\uD83D\uDDD1\uFE0F Clear" })] })] }), _jsxs("div", { className: "chat-messages", children: [messages.map((msg, idx) => (_jsxs("div", { className: `message message-${msg.role}`, children: [_jsx("div", { className: "message-role", children: msg.role === 'user' ? '👤 You' : '🤖 Agent' }), _jsx("div", { className: "message-content", children: msg.content }), _jsx("div", { className: "message-time", children: new Date(msg.timestamp).toLocaleTimeString() })] }, msg.id))), isSending && (_jsxs("div", { className: "message message-assistant", children: [_jsx("div", { className: "message-role", children: "\uD83E\uDD16 Agent" }), _jsxs("div", { className: "message-content typing", children: [_jsx("span", {}), _jsx("span", {}), _jsx("span", {})] })] })), _jsx("div", { ref: messagesEndRef })] }), _jsxs("div", { className: "chat-input-area", children: [_jsx("input", { type: "text", value: input, onChange: (e) => setInput(e.target.value), onKeyPress: (e) => {
                                        if (e.key === 'Enter' && !isSending)
                                            sendMessage();
                                    }, placeholder: "Type a message...", disabled: isSending, className: "chat-input" }), _jsxs("button", { onClick: sendMessage, disabled: isSending || !input.trim(), className: `btn btn-primary ${isSending ? 'disabled' : ''}`, children: [isSending ? '⏳' : '📤', " Send"] })] })] })) })] }));
}
