import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
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
  useI18n()

  const trace = data.trace

  return (
    <div>
      <div className="card">
        <h2>{t("core.Trace.event_trace_f422f3")}</h2>
        <div className="grid">
          <div className="metric">
            <label>{t("core.Trace.total_events_1f9437")}</label>
            <div>{trace.event_count}</div>
          </div>
          <div className="metric">
            <label>{t("core.Trace.cost_usd_2402e8")}</label>
            <div>${formatNumber(trace.cost_usd,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
          </div>
          <div className="metric">
            <label>{t("core.Trace.trace_id_c4cbbc")}</label>
            <div>{trace.trace_id}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>{t("core.Trace.event_timeline_50c4cd")}</h2>
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
                  <summary>{t("core.Trace.attributes_4b0ed8")}</summary>
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
                  <summary>{t("core.presentation.evidenceCount",{count:formatNumber(event.evidence_refs.length)})}</summary>
                  <ul className="evidence-list">
                    {event.evidence_refs.map((ref: string, ridx: number) => (
                      <li key={ridx} className="evidence-item">{ref}</li>
                    ))}
                  </ul>
                </details>
              )}
              <p>{' '}{t("core.Trace.sequence_0f7a6b")}{' '}{event.sequence}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>{t("core.Trace.all_evidence_references_8ee6bc")}</h2>
        <ul className="evidence-list">
          {(trace.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
