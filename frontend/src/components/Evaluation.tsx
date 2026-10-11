import './Evaluation.css'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

interface Props {
  data: Artifacts
}

export default function Evaluation({ data }: Props) {
  const evaluation = data.evaluation

  return (
    <div>
      <div className="card">
        <h2>Governance Evaluation</h2>
        <div className="grid">
          <div className="metric">
            <label>Status</label>
            <div>
              <span className={`badge ${evaluation.status === 'PASS' ? 'success' : 'error'}`}>
                {evaluation.status}
              </span>
            </div>
          </div>
          <div className="metric">
            <label>Score</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{(evaluation.score * 100).toFixed(0)}%</div>
          </div>
          <div className="metric">
            <label>Cost (USD)</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>${evaluation.cost_usd.toFixed(2)}</div>
          </div>
          <div className="metric">
            <label>Checks Passed</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{evaluation.checks?.filter((c: any) => c.passed).length || 0} / {evaluation.checks?.length || 0}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Governance Checks</h2>
        <div className="timeline">
          {(evaluation.checks || []).map((check: any, idx: number) => (
            <div key={idx} className={`timeline-item ${check.passed ? 'success' : 'error'}`}>
              <strong>{check.name}</strong>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.9em', color: 'rgba(255, 255, 255, 0.8)' }}>
                {check.detail}
              </p>
              {check.evidence_refs && check.evidence_refs.length > 0 && (
                <details style={{ marginTop: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontSize: '0.9em' }}>Evidence ({check.evidence_refs.length})</summary>
                  <ul className="evidence-list" style={{ marginTop: '8px' }}>
                    {check.evidence_refs.map((ref: string, ridx: number) => (
                      <li key={ridx} className="evidence-item">{ref}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>What Was Validated</h2>
        <ul style={{ marginLeft: '20px' }}>
          <li>✓ Trace root event exists</li>
          <li>✓ All governance workflow stages present (intent → retrieval → authorization → execution → verification)</li>
          <li>✓ Retrieval hits are linked to citations</li>
          <li>✓ Tool requests retain authorization linkage (permits)</li>
          <li>✓ Executions and receipts are linked to evidence</li>
          <li>✓ No unauthorized effects executed</li>
          <li>✓ Sandbox execution has a receipt</li>
        </ul>
      </div>

      <div className="card">
        <h2>Interpretation</h2>
        <p>
          A <strong>PASS</strong> evaluation means:
        </p>
        <ul style={{ marginLeft: '20px' }}>
          <li>The governed workflow executed end-to-end</li>
          <li>All evidence artifacts are properly linked</li>
          <li>No tool executed without an explicit permit</li>
          <li>The retrieval chain is reproducible and auditable</li>
          <li>Authorization boundaries were respected</li>
        </ul>
      </div>

      <div className="card">
        <h2>All Evidence References</h2>
        <ul className="evidence-list">
          {(evaluation.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
