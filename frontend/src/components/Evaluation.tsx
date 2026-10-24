import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber,stateLabel} from '../i18n'
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
  useI18n()

  const evaluation = data.evaluation

  return (
    <div>
      <div className="card">
        <h2>{t("core.Evaluation.governance_evaluation_614b0c")}</h2>
        <div className="grid">
          <div className="metric">
            <label>{t("core.Evaluation.status_920e41")}</label>
            <div>
              <span className={`badge ${evaluation.status === 'PASS' ? 'success' : 'error'}`}>
                {stateLabel(evaluation.status)}
              </span>
            </div>
          </div>
          <div className="metric">
            <label>{t("core.Evaluation.score_38e5a4")}</label>
            <div>{formatNumber(evaluation.score * 100,{maximumFractionDigits:0})}%</div>
          </div>
          <div className="metric">
            <label>{t("core.Evaluation.cost_usd_2402e8")}</label>
            <div>${formatNumber(evaluation.cost_usd,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
          </div>
          <div className="metric">
            <label>{t("core.Evaluation.checks_passed_fc774c")}</label>
            <div>{evaluation.checks?.filter((c: any) => c.passed).length || 0} / {evaluation.checks?.length || 0}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>{t("core.Evaluation.governance_checks_fe83c4")}</h2>
        <div className="timeline">
          {(evaluation.checks || []).map((check: any, idx: number) => (
            <div key={idx} className={`timeline-item ${check.passed ? 'success' : 'error'}`}>
              <strong>{check.name}</strong>
              <p>
                {check.detail}
              </p>
              {check.evidence_refs && check.evidence_refs.length > 0 && (
                <details>
                  <summary>{t("core.presentation.evidenceCount",{count:formatNumber(check.evidence_refs.length)})}</summary>
                  <ul className="evidence-list">
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
        <h2>{t("core.Evaluation.what_was_validated_9f3253")}</h2>
        <ul>
          <li>{t("core.Evaluation.trace_root_event_exists_5f9f6f")}</li>
          <li>{t("core.Evaluation.all_governance_stages_are_present_intent_retrieval_cba6fd")}</li>
          <li>{t("core.Evaluation.retrieval_hits_are_linked_to_citations_11a6eb")}</li>
          <li>{t("core.Evaluation.tool_requests_retain_authorization_linkage_permits_d99247")}</li>
          <li>{t("core.Evaluation.executions_and_receipts_are_linked_to_evidence_45fbf2")}</li>
          <li>{t("core.Evaluation.no_unauthorized_effects_executed_511b9c")}</li>
          <li>{t("core.Evaluation.sandbox_execution_has_a_receipt_3e39ef")}</li>
        </ul>
      </div>

      <div className="card">
        <h2>{t("core.Evaluation.interpretation_d5da11")}</h2>
        <p>{t("core.presentation.passInterpretation",{state:"PASS"})}</p>
        <ul>
          <li>{t("core.Evaluation.the_governed_workflow_executed_end_to_end_85cd0c")}</li>
          <li>{t("core.Evaluation.all_evidence_artifacts_are_properly_linked_245538")}</li>
          <li>{t("core.Evaluation.no_tool_executed_without_an_explicit_permit_170893")}</li>
          <li>{t("core.Evaluation.the_retrieval_chain_is_reproducible_and_auditable_6ece15")}</li>
          <li>{t("core.Evaluation.authorization_boundaries_were_respected_6453e1")}</li>
        </ul>
      </div>

      <div className="card">
        <h2>{t("core.Evaluation.all_evidence_references_8ee6bc")}</h2>
        <ul className="evidence-list">
          {(evaluation.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
