import { t, useI18n } from '../i18n'
import ExternalConnections from './ExternalConnections'

export default function ToolsConnectionsView() {
  useI18n()
  return <section className="tools-connections-view" aria-label={t('commerce.capability_ui.connections')}>
    <header className="service-surface-header">
      <h1>{t('commerce.capability_ui.connections')}</h1>
      <p>{t('commerce.tools_connections_description')}</p>
      <p>{t('commerce.tools_agent_assignment_description')}</p>
    </header>
    <ExternalConnections />
  </section>
}
