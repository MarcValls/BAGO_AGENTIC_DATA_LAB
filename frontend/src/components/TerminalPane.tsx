import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber,stateLabel} from '../i18n'
interface TerminalPaneProps {
  status: string
  exitCode: number | null
  logs: string[]
  emptyMessage: string
}

export default function TerminalPane({ status, exitCode, logs, emptyMessage }: TerminalPaneProps) {
  useI18n()

  return (
    <section className="terminal-pane" aria-label={t("core.TerminalPane.execution_terminal_a2dc30")}>
      <header className="terminal-pane-titlebar">
        <span>{t("core.TerminalPane.output_b2439b")}</span>
        <span className="terminal-pane-status" role="status">{stateLabel(status)}{exitCode !== null ? ` · ${t('common.exitCode')}: ${formatNumber(exitCode)}` : ''}</span>
      </header>
      <div className="terminal-pane-output" aria-live="polite" aria-atomic="false">
        {logs.length === 0 ? <p>{emptyMessage}</p> : logs.map((line, index) => <div className="terminal-pane-line" key={`${index}:${line}`}>{line}</div>)}
      </div>
    </section>
  )
}
