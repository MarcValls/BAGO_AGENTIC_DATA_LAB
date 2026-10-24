import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber,stateLabel} from '../i18n'
import './Authorization.css'
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

export default function Authorization({ data }: Props) {
  useI18n()

  const proposals = data.agent_run.proposals || []
  const providerReceipt = data.receipts.provider_receipt
  const sandboxReceipt = data.receipts.sandbox_receipt

  return (
    <div>
      <div className="card">
        <h2>{t("core.Authorization.authorization_execution_boundary_211249")}</h2>
        <p>{' '}{t("core.Authorization.bago_authorization_requires_permit_issuance_for_every_5ead4f")}{' '}</p>
      </div>

      <div className="card">
        <h2>{t("core.Authorization.tool_proposals_d08fc7")}</h2>
        {proposals.map((proposal: any, idx: number) => (
          <div key={idx} className="card">
            <div className="grid">
              <div className="metric">
                <label>{t("core.Authorization.tool_2e53bd")}</label>
                <div>{proposal.tool_name}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.decision_640ae4")}</label>
                <div>
                  <span className={`badge ${proposal.decision === 'ALLOW' ? 'success' : 'error'}`}>
                    {stateLabel(proposal.decision)}
                  </span>
                </div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.effect_type_55b019")}</label>
                <div>{stateLabel(proposal.effect_type)}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.status_920e41")}</label>
                <div>
                  <span className={`badge ${proposal.outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                    {proposal.outcome}
                  </span>
                </div>
              </div>
            </div>
            <p><strong>{t("core.Authorization.permit_id_9c42e5")}</strong> {proposal.permit_id}</p>
            <p><strong>{t("core.Authorization.request_id_816d7f")}</strong> {proposal.request_id}</p>
            <p><strong>{t("core.Authorization.rationale_766469")}</strong> {proposal.rationale}</p>
            {proposal.result && (
              <div>
                <p><strong>{t("core.Authorization.result_ccfbca")}</strong></p>
                <p>{proposal.result}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h2>{t("core.Authorization.provider_receipt_bedrock_dbe993")}</h2>
        {providerReceipt && (
          <div className="grid">
            <div className="metric">
              <label>{t("core.Authorization.status_920e41")}</label>
              <div>
                <span className={`badge ${providerReceipt.execution_outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                  {stateLabel(providerReceipt.execution_outcome)}
                </span>
              </div>
            </div>
            <div className="metric">
              <label>{t("core.Authorization.decision_640ae4")}</label>
              <div>
                <span className={`badge ${providerReceipt.decision === 'ALLOW' ? 'success' : 'error'}`}>
                  {stateLabel(providerReceipt.decision)}
                </span>
              </div>
            </div>
            <div className="metric">
              <label>{t("core.Authorization.cost_usd_2402e8")}</label>
              <div>${formatNumber(providerReceipt.cost_usd,{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
            </div>
            <div className="metric">
              <label>{t("core.Authorization.duration_ms_35d6a4")}</label>
              <div>{providerReceipt.duration_ms}</div>
            </div>
            <div className="metric">
              <label>{t("core.Authorization.input_tokens_c54a41")}</label>
              <div>{providerReceipt.usage?.input_tokens || 0}</div>
            </div>
            <div className="metric">
              <label>{t("core.Authorization.output_tokens_a0a107")}</label>
              <div>{providerReceipt.usage?.output_tokens || 0}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h2>{t("core.Authorization.sandbox_receipt_05dc83")}</h2>
        {sandboxReceipt && (
          <div>
            <div className="grid">
              <div className="metric">
                <label>{t("core.Authorization.status_920e41")}</label>
                <div>
                  <span className={`badge ${sandboxReceipt.status === 'SUCCESS' ? 'success' : 'error'}`}>
                    {stateLabel(sandboxReceipt.status)}
                  </span>
                </div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.profile_d696a3")}</label>
                <div>{sandboxReceipt.profile}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.capability_5faf58")}</label>
                <div>{sandboxReceipt.capability}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.exit_code_60e19d")}</label>
                <div>{sandboxReceipt.exit_code}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.duration_ms_35d6a4")}</label>
                <div>{sandboxReceipt.duration_ms}</div>
              </div>
              <div className="metric">
                <label>{t("core.Authorization.network_1744b9")}</label>
                <div>{sandboxReceipt.network_mode}</div>
              </div>
            </div>
            <p><strong>{t("core.Authorization.sandbox_id_369297")}</strong> {sandboxReceipt.sandbox_id}</p>
            <p><strong>{t("core.Authorization.permit_id_9c42e5")}</strong> {sandboxReceipt.permit_id}</p>
          </div>
        )}
      </div>
    </div>
  )
}
