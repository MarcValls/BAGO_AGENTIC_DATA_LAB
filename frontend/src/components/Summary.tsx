import './Summary.css'

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

export default function Summary({ data }: Props) {
  const s = data.summary

  return (
    <div>
      <div className="grid">
        <div className="metric">
          <label>Status</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>
            <span className={`badge ${s.status === 'PASS' ? 'success' : 'error'}`}>
              {s.status}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>Case</label>
          <div style={{ fontSize: '1em' }}>{s.case}</div>
        </div>
        <div className="metric">
          <label>Client</label>
          <div style={{ fontSize: '1em' }}>{s.client}</div>
        </div>
        <div className="metric">
          <label>Tests Passed</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{s.evaluation_checks?.filter((c: any) => c.passed).length || 0} / {s.evaluation_checks?.length || 0}</div>
        </div>
        <div className="metric">
          <label>Cost (USD)</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>${s.cost_usd.toFixed(2)}</div>
        </div>
        <div className="metric">
          <label>Retrieval Hits</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{s.retrieval_hits}</div>
        </div>
        <div className="metric">
          <label>Ontology Paths</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{s.ontology_paths}</div>
        </div>
        <div className="metric">
          <label>Ontology Status</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>
            <span className={`badge ${s.ontology_outcome === 'SUCCESS' ? 'success' : 'error'}`}>
              {s.ontology_outcome}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>Sandbox Status</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>
            <span className={`badge ${s.sandbox_status === 'SUCCESS' ? 'success' : 'error'}`}>
              {s.sandbox_status}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>Trace Events</label>
          <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{s.trace_events}</div>
        </div>
      </div>

      <div className="card">
        <h3>Query</h3>
        <p>{data.agent_run.query}</p>
      </div>

      <div className="card">
        <h3>Answer</h3>
        <p>{data.agent_run.answer}</p>
      </div>

      <div className="card">
        <h3>Citations</h3>
        <ul className="evidence-list">
          {(data.agent_run.citations || []).map((c: string, idx: number) => (
            <li key={idx} className="evidence-item">{c}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Scope</h3>
        <p>{s.scope}</p>
        {s.aws_live !== 'VERIFIED' && (
          <p style={{ fontSize: '0.9em', color: 'rgba(255, 255, 255, 0.6)' }}>
            AWS Live: {s.aws_live}
          </p>
        )}
        {s.openmetadata_live !== 'VERIFIED' && (
          <p style={{ fontSize: '0.9em', color: 'rgba(255, 255, 255, 0.6)' }}>
            OpenMetadata Live: {s.openmetadata_live}
          </p>
        )}
      </div>
    </div>
  )
}
