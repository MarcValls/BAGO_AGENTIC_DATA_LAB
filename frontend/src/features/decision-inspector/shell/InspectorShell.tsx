import { useState, type ReactNode } from 'react'
import type { DecisionConclusion } from '../../../contracts/decision/evidence'
import { InspectorStateView, type InspectorState } from '../shared/InspectorState'
import './InspectorShell.css'

export type InspectorSection = 'conclusion' | 'claims' | 'evidence' | 'provenance'
export type InspectorSectionContent = Partial<Record<InspectorSection, ReactNode>>

export function selectConclusion<T extends Pick<DecisionConclusion, 'id'>>(items: T[], id: string | null): T | undefined {
  return id == null ? undefined : items.find(item => item.id === id)
}

export interface InspectorShellProps {
  conclusions: DecisionConclusion[]
  selectedConclusionId?: string | null
  onConclusionSelect?: (id: string) => void
  state?: InspectorState
  sections?: InspectorSectionContent
  initialSection?: InspectorSection
}

const sectionLabels: Record<InspectorSection, string> = {
  conclusion: 'Conclusion', claims: 'Claims', evidence: 'Evidence', provenance: 'Provenance',
}

export function InspectorShell({ conclusions, selectedConclusionId, onConclusionSelect, state = { status: 'ready' }, sections = {}, initialSection = 'conclusion' }: InspectorShellProps) {
  const [internalId, setInternalId] = useState<string | null>(null)
  const [section, setSection] = useState<InspectorSection>(initialSection)
  const activeId = selectedConclusionId === undefined ? internalId : selectedConclusionId
  const selected = selectConclusion(conclusions, activeId)
  const choose = (id: string) => {
    setInternalId(id)
    onConclusionSelect?.(id)
    setSection('conclusion')
  }

  return (
    <main className="decision-inspector" aria-labelledby="decision-inspector-title">
      <header className="decision-inspector__header">
        <h1 id="decision-inspector-title">Decision Inspector</h1>
        {selected?.runId && <p className="decision-inspector__identity"><span>Run ID:</span> <code>{selected.runId}</code></p>}
      </header>

      {conclusions.length > 0 && <nav className="decision-inspector__selection" aria-label="Select a conclusion">
        <ul>{conclusions.map(conclusion => (
          <li key={conclusion.id}>
            <button type="button" aria-current={selected?.id === conclusion.id ? 'true' : undefined} onClick={() => choose(conclusion.id)}>
              {conclusion.text || `Conclusion ${conclusion.id}`}
            </button>
          </li>
        ))}</ul>
      </nav>}

      <InspectorStateView state={conclusions.length === 0 && state.status === 'ready' ? { status: 'empty', message: 'No conclusions were provided by the source.' } : state}>
        {selected ? <>
          <p className="decision-inspector__breadcrumb" aria-label="Current location">Run {selected.runId || 'Not provided'} <span aria-hidden="true">›</span> {sectionLabels[section]}</p>
          <nav className="decision-inspector__sections" aria-label="Conclusion details">
            {(Object.keys(sectionLabels) as InspectorSection[]).map(key => (
              <button type="button" key={key} aria-pressed={section === key} onClick={() => setSection(key)}>{sectionLabels[key]}</button>
            ))}
          </nav>
          <section className="decision-inspector__content" aria-labelledby="decision-inspector-section-title">
            <h2 id="decision-inspector-section-title">{sectionLabels[section]}</h2>
            {sections[section] ?? <p>{section === 'conclusion' ? selected.text : `${sectionLabels[section]} data not provided.`}</p>}
          </section>
        </> : conclusions.length > 0 && <InspectorStateView state={{ status: 'unknown', message: activeId ? `Conclusion ${activeId} was not found in the supplied data.` : 'Select a conclusion to inspect it.' }} />}
      </InspectorStateView>
    </main>
  )
}
