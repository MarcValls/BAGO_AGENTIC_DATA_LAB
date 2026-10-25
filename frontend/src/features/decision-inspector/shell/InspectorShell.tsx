import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../../i18n'
import './InspectorShell.css'
import { useState, type ReactNode } from 'react'
import type { DecisionConclusion } from '../../../contracts/decision/evidence'
import { InspectorStateView, type InspectorState } from '../shared/InspectorState'

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
  embedded?: boolean
  initialSection?: InspectorSection
}

const sectionLabels: Record<InspectorSection, string> = {
  get conclusion() { return t('agents.InspectorShell.conclusion') }, get claims() { return t('agents.EvidenceExplorer.claims') }, get evidence() { return t('agents.EvidenceExplorer.evidence') }, get provenance() { return t('agents.InspectorShell.provenance') },
}

export function InspectorShell({ conclusions, selectedConclusionId, onConclusionSelect, state = { status: 'ready' }, sections = {}, initialSection = 'conclusion', embedded = false }: InspectorShellProps) {
  useI18n()
  const [internalId, setInternalId] = useState<string | null>(null)
  const [section, setSection] = useState<InspectorSection>(initialSection)
  const activeId = selectedConclusionId === undefined ? internalId : selectedConclusionId
  const selected = selectConclusion(conclusions, activeId)
  const choose = (id: string) => {
    setInternalId(id)
    onConclusionSelect?.(id)
    setSection('conclusion')
  }

  const Surface = embedded ? 'section' : 'main'
  return (
    <Surface className="decision-inspector" aria-labelledby={embedded ? undefined : "decision-inspector-title"} aria-label={embedded ? t('agents.InspectorShell.conclusion_details') : undefined}>
      {!embedded&&<header className="decision-inspector__header">
        <h1 id="decision-inspector-title">{t('agents.DecisionInspector.decision_inspector')}</h1>
        {selected?.runId && <p className="decision-inspector__identity"><span>{t('agents.ActionReview.run_id')}</span> <code>{selected.runId}</code></p>}
      </header>}

      {(embedded ? conclusions.length > 1 : conclusions.length > 0) && <nav className="decision-inspector__selection" aria-label={t('agents.InspectorShell.select_a_conclusion')}>
        <ul>{conclusions.map(conclusion => (
          <li key={conclusion.id}>
            <button type="button" aria-current={selected?.id === conclusion.id ? 'true' : undefined} onClick={() => choose(conclusion.id)}>
              {conclusion.text || t('agents.InspectorShell.conclusion_p0', {p0: conclusion.id})}
            </button>
          </li>
        ))}</ul>
      </nav>}

      <InspectorStateView state={conclusions.length === 0 && state.status === 'ready' ? { status: 'empty', message: t('agents.InspectorShell.no_conclusions_were_provided_by_the_source') } : state}>
        {selected ? <>
          <p className="decision-inspector__breadcrumb" aria-label={t('agents.InspectorShell.current_location')}>{!embedded&&<>{t('agents.InspectorShell.run')} {selected.runId || t('agents.AgentRunner.not_provided')} <span aria-hidden="true">›</span> </>} {sectionLabels[section]}</p>
          <nav className="decision-inspector__sections" aria-label={t('agents.InspectorShell.conclusion_details')}>
            {(Object.keys(sectionLabels) as InspectorSection[]).map(key => (
              <button type="button" key={key} aria-pressed={section === key} onClick={() => setSection(key)}>{sectionLabels[key]}</button>
            ))}
          </nav>
          <section className="decision-inspector__content" aria-labelledby="decision-inspector-section-title">
            <h2 id="decision-inspector-section-title">{sectionLabels[section]}</h2>
            {sections[section] ?? <p>{section === 'conclusion' ? selected.text : t('agents.InspectorShell.p0_data_not_provided', {p0: sectionLabels[section]})}</p>}
          </section>
        </> : conclusions.length > 0 && <InspectorStateView state={{ status: 'unknown', message: activeId ? t('agents.InspectorShell.conclusion_p0_was_not_found_in_the_supplied_data', {p0: activeId}) : t('agents.InspectorShell.select_a_conclusion_to_inspect_it') }} />}
      </InspectorStateView>
    </Surface>
  )
}
