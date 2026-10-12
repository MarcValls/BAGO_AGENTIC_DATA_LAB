import './Control.css'
import './WindowsSurface.css'
import { useState } from 'react'
import TerminalPane from './TerminalPane'
import WindowPanel from './WindowPanel'

interface Props {
  onDemoRun?: () => void
}

export default function Control({ onDemoRun }: Props) {
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [writeEvidence, setWriteEvidence] = useState(false)
  const [jsonOutput, setJsonOutput] = useState(false)
  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle')
  const [exitCode, setExitCode] = useState<number | null>(null)

  const runDemoWebSocket = async () => {
    setIsRunning(true)
    setLogs([])
    setStatus('running')
    setExitCode(null)

    try {
      const websocketUrl = new URL('/ws/demo/run', window.location.href)
      websocketUrl.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(websocketUrl)

      ws.onopen = () => {
        ws.send(JSON.stringify({
          write_evidence: writeEvidence,
          json_output: jsonOutput,
        }))
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'stdout') {
          setLogs((prev) => [...prev, msg.data])
        } else if (msg.type === 'done') {
          setExitCode(msg.exit_code)
          setStatus(msg.exit_code === 0 ? 'success' : 'error')
          setIsRunning(false)
          ws.close()
          if (onDemoRun) onDemoRun()
        } else if (msg.type === 'error') {
          setLogs((prev) => [...prev, `ERROR: ${msg.data}`])
          setStatus('error')
          setIsRunning(false)
          ws.close()
        }
      }

      ws.onerror = (error) => {
        setLogs((prev) => [...prev, `WebSocket error: ${error}`])
        setStatus('error')
        setIsRunning(false)
      }

      ws.onclose = () => {
        if (status === 'running') {
          setStatus('error')
          setIsRunning(false)
        }
      }
    } catch (error) {
      setLogs((prev) => [...prev, `Connection error: ${error}`])
      setStatus('error')
      setIsRunning(false)
    }
  }

  const runDemoHTTP = async () => {
    setIsRunning(true)
    setLogs([])
    setStatus('running')
    setExitCode(null)

    try {
      const response = await fetch('/api/demo/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          write_evidence: writeEvidence,
          json_output: jsonOutput,
        }),
      })

      const data = await response.json()
      setLogs((data.stdout + '\n' + data.stderr).split('\n').filter(Boolean))
      setExitCode(data.exit_code)
      setStatus(data.exit_code === 0 ? 'success' : 'error')
      setIsRunning(false)
      if (onDemoRun) onDemoRun()
    } catch (error) {
      setLogs((prev) => [...prev, `Error: ${error}`])
      setStatus('error')
      setIsRunning(false)
    }
  }

  const downloadLogs = () => {
    const content = logs.join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `demo-logs-${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const clearLogs = () => {
    setLogs([])
  }

  return (
    <div className="control-container">
      <WindowPanel title="Demo orchestration" description="Run and inspect the existing demo" className="control-panel">

        <div className="control-section">
          <h3>Execute Demo</h3>
          <div className="control-options">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={writeEvidence}
                onChange={(e) => setWriteEvidence(e.target.checked)}
                disabled={isRunning}
              />
              Write Evidence Bundle
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={jsonOutput}
                onChange={(e) => setJsonOutput(e.target.checked)}
                disabled={isRunning}
              />
              JSON Output
            </label>
          </div>

          <div className="button-group">
            <button
              onClick={runDemoWebSocket}
              disabled={isRunning}
              className={`btn btn-primary ${isRunning ? 'disabled' : ''}`}
            >
              {isRunning ? 'Running...' : 'Run demo (WebSocket)'}
            </button>
            <button
              onClick={runDemoHTTP}
              disabled={isRunning}
              className={`btn btn-secondary ${isRunning ? 'disabled' : ''}`}
            >
              {isRunning ? 'Running...' : 'Run demo (HTTP)'}
            </button>
          </div>
        </div>

        <div className="status-section">
          <div className={`status-badge ${status}`}>
            {status === 'idle' && 'Idle'}
            {status === 'running' && 'Running'}
            {status === 'success' && 'Success'}
            {status === 'error' && 'Error'}
          </div>
          {exitCode !== null && (
            <div className="exit-code">Exit Code: <strong>{exitCode}</strong></div>
          )}
        </div>

        <div className="logs-section">
          <div className="logs-header">
            <h3>Execution Logs</h3>
            <div className="logs-actions">
              <button onClick={clearLogs} className="btn btn-small" disabled={isRunning}>
                Clear
              </button>
              <button onClick={downloadLogs} className="btn btn-small" disabled={logs.length === 0}>
                Download
              </button>
            </div>
          </div>
          <TerminalPane status={status} exitCode={exitCode} logs={logs} emptyMessage="No logs yet. Run demo to see output." />
        </div>
      </WindowPanel>

      <div className="control-sidebar">
        <div className="card">
          <h3>Quick Info</h3>
          <p><strong>Endpoint:</strong> {window.location.origin}</p>
          <p><strong>WebSocket:</strong> {window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//{window.location.host}/ws/demo/run</p>
          <p><strong>API:</strong> /api/demo/run (POST)</p>
        </div>

        <div className="card">
          <h3>What This Does</h3>
          <ul>
            <li>Executes <code>python demo.py</code></li>
            <li>Streams logs in real time</li>
            <li>Captures exit code</li>
            <li>Optional evidence bundle</li>
            <li>Optional JSON output</li>
            <li>Downloadable logs</li>
          </ul>
        </div>

        <div className="card">
          <h3>Next Steps</h3>
          <ul>
            <li>1. Run demo via this panel</li>
            <li>2. Check logs for errors</li>
            <li>3. Refresh Summary tab</li>
            <li>4. View results</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
