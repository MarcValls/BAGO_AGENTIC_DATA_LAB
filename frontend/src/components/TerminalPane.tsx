interface TerminalPaneProps {
  status: string
  exitCode: number | null
  logs: string[]
  emptyMessage: string
}

export default function TerminalPane({ status, exitCode, logs, emptyMessage }: TerminalPaneProps) {
  return (
    <section className="terminal-pane" aria-label="Execution terminal">
      <header className="terminal-pane-titlebar">
        <span>Output</span>
        <span className="terminal-pane-status" role="status">{status}{exitCode !== null ? ` · exit ${exitCode}` : ''}</span>
      </header>
      <div className="terminal-pane-output" aria-live="polite" aria-atomic="false">
        {logs.length === 0 ? <p>{emptyMessage}</p> : logs.map((line, index) => <div className="terminal-pane-line" key={`${index}:${line}`}>{line}</div>)}
      </div>
    </section>
  )
}
