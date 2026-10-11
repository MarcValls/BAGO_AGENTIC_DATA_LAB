import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import type { DecisionConclusion } from '../../../../src/contracts/decision/evidence'
import { EvidenceExplorer } from '../../../../src/features/decision-inspector/evidence/EvidenceExplorer'

const conclusion: DecisionConclusion = {
  schema: 'decision-conclusion/v1', id: 'conclusion-1', runId: 'run-42', text: 'Source-provided conclusion',
  claims: [
    { id: 'claim-supported', text: 'A source-backed claim', evidence: [{ evidenceId: 'evidence-1', relation: 'supports' }] },
    { id: 'claim-unsupported', text: 'A claim without linked evidence', evidence: [] },
    { id: 'claim-missing', text: 'A claim with an unresolved reference', evidence: [{ evidenceId: 'evidence-404', relation: 'supports' }] },
    { id: 'claim-conflict', text: 'A claim with a reported contradiction', evidence: [{ evidenceId: 'evidence-1', relation: 'contradicts' }] },
    { id: 'claim-context', text: 'A claim with context-only evidence', evidence: [{ evidenceId: 'evidence-1', relation: 'context_only' }] },
  ],
  evidence: [{
    id: 'evidence-1', artifactRef: 'citation-1', sourceIdentity: 'local://source/doc-7',
    snapshot: { sourceUri: 'local://source/doc-7', revision: 'rev-2', documentId: 'doc-7', chunkId: 'chunk-9' },
    freshness: 'unknown', contentFingerprint: 'sha256:provided-only', excerpt: 'Source-provided excerpt.',
  }],
}

test('renders source-provided claim tree, evidence viewer and full available provenance', () => {
  const html = renderToStaticMarkup(<EvidenceExplorer conclusion={conclusion} initialClaimId="claim-supported" />)
  for (const value of ['A source-backed claim', 'Supported by linked evidence', 'Evidence reference', 'citation-1', 'local://source/doc-7', 'rev-2', 'doc-7', 'chunk-9', 'sha256:provided-only', 'Freshness not established', 'Source-provided excerpt.']) assert.match(html, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.match(html, /aria-pressed="true"/)
  assert.match(html, /Run ID:/)
})

test('explicitly distinguishes unsupported, missing and contradictory claim evidence', () => {
  const html = renderToStaticMarkup(<EvidenceExplorer conclusion={conclusion} initialClaimId="claim-missing" />)
  assert.match(html, /No supporting evidence linked/)
  assert.match(html, /Referenced evidence <code>evidence-404<\/code> is unavailable/)
  assert.match(html, /Conflicting evidence is reported/)
  const contextHtml = renderToStaticMarkup(<EvidenceExplorer conclusion={conclusion} initialClaimId="claim-context" />)
  assert.match(contextHtml, /Linked records are context-only or marked insufficient/)
  assert.match(contextHtml, /Evidence support is unknown/)
})

test('does not create claims from conclusion text when structured claims are absent', () => {
  const noClaims = { ...conclusion, claims: [] }
  const html = renderToStaticMarkup(<EvidenceExplorer conclusion={noClaims} />)
  assert.match(html, /Claims not provided/)
  assert.match(html, /Citations are not converted into claims/)
  assert.doesNotMatch(html, /A source-backed claim/)
})

test('uses explicit expected snapshot for freshness and preserves stale references', () => {
  const html = renderToStaticMarkup(<EvidenceExplorer
    conclusion={conclusion}
    initialClaimId="claim-supported"
    expectedSnapshot={{ sourceUri: 'local://source/doc-7', revision: 'rev-3' }}
  />)
  assert.match(html, /Freshness: Stale/)
  assert.match(html, /At least one linked evidence snapshot is stale/)
  assert.match(html, /rev-2/)
})

test('loading, error, unsupported and empty state messages remain accessible', () => {
  const states = [
    [{ status: 'loading' as const }, /Loading run artifacts/],
    [{ status: 'error' as const, message: 'Evidence request failed' }, /Evidence request failed/],
    [{ status: 'unsupported' as const, message: 'Evidence schema unsupported' }, /Evidence schema unsupported/],
    [{ status: 'empty' as const, message: 'No evidence records returned' }, /No evidence records returned/],
  ] as const
  for (const [state, expected] of states) {
    const html = renderToStaticMarkup(<EvidenceExplorer conclusion={conclusion} state={state} />)
    assert.match(html, /role="(status|alert)"/)
    assert.match(html, expected)
  }
})
