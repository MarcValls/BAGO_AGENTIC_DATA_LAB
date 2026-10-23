import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber,stateLabel} from '../i18n'
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
  useI18n()

  const s = data.summary

  return (
    <div>
      <div className="grid">
        <div className="metric">
          <label>{t("core.Summary.status_920e41")}</label>
          <div>
            <span className={`badge ${s.status === 'PASS' ? 'success' : 'error'}`}>
              {stateLabel(s.status)}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.case_15f86e")}</label>
          <div>{s.case}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.client_0c77fe")}</label>
          <div>{s.client}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.tests_passed_116e14")}</label>
          <div>{s.evaluation_checks?.filter((c: any) => c.passed).length || 0} / {s.evaluation_checks?.length || 0}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.cost_usd_2402e8")}</label>
          <div>${formatNumber(s.cost_usd,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.retrieval_hits_610cdf")}</label>
          <div>{s.retrieval_hits}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.ontology_paths_a345f9")}</label>
          <div>{s.ontology_paths}</div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.ontology_status_0c7782")}</label>
          <div>
            <span className={`badge ${s.ontology_outcome === 'SUCCESS' ? 'success' : 'error'}`}>
              {stateLabel(s.ontology_outcome)}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.sandbox_status_a45965")}</label>
          <div>
            <span className={`badge ${s.sandbox_status === 'SUCCESS' ? 'success' : 'error'}`}>
              {stateLabel(s.sandbox_status)}
            </span>
          </div>
        </div>
        <div className="metric">
          <label>{t("core.Summary.trace_events_b5ef09")}</label>
          <div>{s.trace_events}</div>
        </div>
      </div>

      <div className="card">
        <h3>{t("core.Summary.query_b80a37")}</h3>
        <p>{data.agent_run.query}</p>
      </div>

      <div className="card">
        <h3>{t("core.Summary.answer_b2a3aa")}</h3>
        <p>{data.agent_run.answer}</p>
      </div>

      <div className="card">
        <h3>{t("core.Summary.citations_636d02")}</h3>
        <ul className="evidence-list">
          {(data.agent_run.citations || []).map((c: string, idx: number) => (
            <li key={idx} className="evidence-item">{c}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>{t("core.Summary.scope_b073f6")}</h3>
        <p>{s.scope}</p>
        {s.aws_live !== 'VERIFIED' && (
          <p>{' '}{t("core.Summary.aws_live_2aaceb")}{' '}{stateLabel(s.aws_live)}
          </p>
        )}
        {s.openmetadata_live !== 'VERIFIED' && (
          <p>{' '}{t("core.Summary.openmetadata_live_4da47c")}{' '}{stateLabel(s.openmetadata_live)}
          </p>
        )}
      </div>
    </div>
  )
}
