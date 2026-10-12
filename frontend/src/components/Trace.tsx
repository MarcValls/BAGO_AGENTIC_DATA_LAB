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
            <div>{trace.event_count}</div>
          </div>
          <div className="metric">
            <label>Cost (USD)</label>
            <div>${trace.cost_usd.toFixed(2)}</div>
          </div>
          <div className="metric">
            <label>Trace ID</label>
            <div>{trace.trace_id}</div>
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
              <div>
                <strong>{event.name}</strong>
                <span>
                  ({event.kind})
                </span>
              </div>
              {event.attributes && Object.entries(event.attributes).length > 0 && (
                <details>
                  <summary>Attributes</summary>
                  <div>
                    {Object.entries(event.attributes).map(([key, value]: [string, any]) => (
                      <div key={key}>
                        <strong>{key}:</strong> {JSON.stringify(value)}
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {event.evidence_refs && event.evidence_refs.length > 0 && (
                <details>
                  <summary>Evidence ({event.evidence_refs.length})</summary>
                  <ul className="evidence-list">
                    {event.evidence_refs.map((ref: string, ridx: number) => (
                      <li key={ridx} className="evidence-item">{ref}</li>
                    ))}
                  </ul>
                </details>
              )}
              <p>
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
