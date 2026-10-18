import { useState, type FormEvent } from 'react'
import ReactDOM from 'react-dom/client'
import {
  BagoButton,
  BagoDataGrid,
  BagoEmptyState,
  BagoMetric,
  BagoPageHeader,
  BagoPanel,
  BagoStatus,
  BagoTabStrip,
  type BagoGridRow,
} from '../packages/bago-adl-ui-kit/components'
import '../packages/bago-adl-ui-kit/tokens.css'
import '../packages/bago-adl-ui-kit/components.css'
import './ui-kit-preview.css'

type PreviewTab = 'Overview' | 'Runs' | 'Policies'

const tabs: Array<{ id: PreviewTab; label: string }> = [
  { id: 'Overview', label: 'Overview' },
  { id: 'Runs', label: 'Agent runs' },
  { id: 'Policies', label: 'Policies' },
]

const rows: BagoGridRow[] = [
  { id: 'run-2048', cells: ['Customer support triage', 'Completed', '2 min ago'] },
  { id: 'run-2047', cells: ['Invoice extraction', 'Waiting for review', '18 min ago'] },
  { id: 'run-2046', cells: ['Supplier risk summary', 'Running', '31 min ago'] },
]

function UiKitPreview() {
  const [activeTab, setActiveTab] = useState<PreviewTab>('Overview')
  const [selectedRun, setSelectedRun] = useState<string | undefined>(undefined)
  const [actionCount, setActionCount] = useState(0)
  const [submitCount, setSubmitCount] = useState(0)

  const onDemoSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitCount((count) => count + 1)
  }

  return (
    <main className="bago-ui showcase">
      <div className="showcase-topline">
        <a className="showcase-brand" href="/" aria-label="BAGO ADL home">
          <span className="showcase-brand__mark" aria-hidden="true">B</span>
          <span>BAGO <span className="showcase-brand__muted">/ UI SYSTEM</span></span>
        </a>
        <span className="showcase-version">ADL UI Kit <span>0.1.0</span></span>
      </div>

      <BagoPageHeader
        kicker="Reusable interface primitives"
        title="A clear surface for governed work."
        description="A live preview of the buttons, panels, status, tabs, metrics and data grid shipped in the BAGO ADL UI Kit."
        actions={<BagoButton variant="primary" onClick={() => setActionCount((count) => count + 1)}>Run demo action</BagoButton>}
      />

      <section className="showcase-metrics" aria-label="Preview metrics">
        <BagoMetric label="Runs today" value="128" hint="↑ 12% from yesterday" />
        <BagoMetric label="Awaiting review" value="07" hint="Human approval required" />
        <BagoMetric label="Provider health" value={<BagoStatus tone="success">Available</BagoStatus>} hint="Last checked just now" />
      </section>

      <BagoPanel className="showcase-workspace">
        <div className="showcase-workspace__header">
          <div>
            <p className="bago-ui-kicker">Workspace</p>
            <h2>Operations overview</h2>
          </div>
          <BagoStatus tone="info">Local preview · fixture data</BagoStatus>
        </div>

        <BagoTabStrip<PreviewTab> label="Preview sections" items={tabs} value={activeTab} onChange={setActiveTab} />

        {activeTab === 'Overview' ? (
          <div className="showcase-overview">
            <div className="showcase-callout">
              <span className="showcase-callout__icon" aria-hidden="true">✦</span>
              <div>
                <h3>Everything in view, decisions stay yours.</h3>
                <p>Use semantic status and clear actions to make the current state easy to scan.</p>
              </div>
            </div>
            <div className="showcase-statuses" aria-label="Status examples">
              <BagoStatus tone="success">Completed</BagoStatus>
              <BagoStatus tone="warning">Needs review</BagoStatus>
              <BagoStatus tone="danger">Blocked</BagoStatus>
              <BagoStatus tone="neutral">Not run</BagoStatus>
            </div>
          </div>
        ) : activeTab === 'Runs' ? (
          <div className="showcase-runs">
            <BagoDataGrid
              label="Recent agent runs"
              columns={['Agent', 'Status', 'Updated']}
              rows={rows}
              selectedId={selectedRun}
              onSelect={setSelectedRun}
            />
            <p className="showcase-selection" role="status" aria-live="polite">
              {selectedRun ? `Selected run: ${selectedRun}` : 'Choose a row to inspect its selection state.'}
            </p>
          </div>
        ) : (
          <BagoEmptyState
            title="No local policies loaded"
            description="This preview uses fixture data only. Connect a real data source in the consuming application."
            action={<BagoButton variant="secondary" onClick={() => setActiveTab('Overview')}>Back to overview</BagoButton>}
          />
        )}
      </BagoPanel>

      <section className="showcase-lower-grid" aria-label="Button behavior demonstrations">
        <BagoPanel>
          <p className="bago-ui-kicker">Safe defaults</p>
          <h2>Buttons behave as buttons</h2>
          <p className="showcase-copy">The first action has no explicit type. It must not submit its surrounding form.</p>
          <form className="showcase-form" onSubmit={onDemoSubmit}>
            <BagoButton onClick={() => setActionCount((count) => count + 1)}>Default button · action {actionCount}</BagoButton>
            <BagoButton type="submit" variant="ghost">Explicit submit</BagoButton>
          </form>
          <p className="showcase-feedback" role="status" aria-live="polite">Form submissions: {submitCount}</p>
        </BagoPanel>

        <BagoPanel className="showcase-note">
          <p className="bago-ui-kicker">Integration boundary</p>
          <h2>Real components, local fixtures</h2>
          <p className="showcase-copy">This page imports the package source directly. No API, provider or authorization action is connected.</p>
          <div className="showcase-note__footer">
            <BagoStatus tone="neutral">No external effects</BagoStatus>
            <BagoButton variant="secondary" onClick={() => { setActiveTab('Runs'); setSelectedRun(undefined) }}>View run table</BagoButton>
          </div>
        </BagoPanel>
      </section>

      <footer className="showcase-footer">
        <span>Designed for readable, reviewable workflows.</span>
        <span>Source: <code>frontend/packages/bago-adl-ui-kit</code></span>
      </footer>
    </main>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<UiKitPreview />)
