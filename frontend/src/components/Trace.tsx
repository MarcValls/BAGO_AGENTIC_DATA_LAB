import './Trace.css'

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

export default function Trace({ data }: Props) {
  const trace = data.trace

  return (
    <div>
      <div className="card">
        <h2>Event Trace</h2>
        <div className="grid">
          <div className="metric">
            <label>Total Events</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{trace.event_count}</div>
          </div>
          <div className="metric">
            <label>Cost (USD)</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>${trace.cost_usd.toFixed(2)}</div>
          </div>
          <div className="metric">
            <label>Trace ID</label>
            <div style={{ fontSize: '0.85em', wordBreak: 'break-all' }}>{trace.trace_id}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Event Timeline</h2>
        <div className="timeline">
          {(trace.events || []).map((event: any, idx: number) => (
            <div
              key={idx}
              className={`timeline-item ${event.status === 'SUCCESS' || event.status === 'ALLOW' ? 'success' : 'error'}`}
            >
              <div style={{ marginBottom: '8px' }}>
                <strong>{event.name}</strong>
                <span style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.9em', marginLeft: '8px' }}>
                  ({event.kind})
                </span>
              </div>
              {event.attributes && Object.entries(event.attributes).length > 0 && (
                <details style={{ marginBottom: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontSize: '0.9em' }}>Attributes</summary>
                  <div style={{ marginTop: '8px', fontSize: '0.85em' }}>
                    {Object.entries(event.attributes).map(([key, value]: [string, any]) => (
                      <div key={key} style={{ marginBottom: '4px' }}>
                        <strong>{key}:</strong> {JSON.stringify(value)}
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {event.evidence_refs && event.evidence_refs.length > 0 && (
                <details style={{ marginBottom: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontSize: '0.9em' }}>Evidence ({event.evidence_refs.length})</summary>
                  <ul className="evidence-list" style={{ marginTop: '8px' }}>
                    {event.evidence_refs.map((ref: string, ridx: number) => (
                      <li key={ridx} className="evidence-item">{ref}</li>
                    ))}
                  </ul>
                </details>
              )}
              <p style={{ fontSize: '0.85em', color: 'rgba(255, 255, 255, 0.5)', margin: '4px 0 0 0' }}>
                Seq: {event.sequence}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>All Evidence References</h2>
        <ul className="evidence-list">
          {(trace.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
