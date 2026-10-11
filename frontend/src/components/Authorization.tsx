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
  const proposals = data.agent_run.proposals || []
  const providerReceipt = data.receipts.provider_receipt
  const sandboxReceipt = data.receipts.sandbox_receipt

  return (
    <div>
      <div className="card">
        <h2>Authorization & Execution Boundary</h2>
        <p>
          BAGO authorization ensures all tool proposals undergo permit issuance before execution.
        </p>
      </div>

      <div className="card">
        <h2>Tool Proposals</h2>
        {proposals.map((proposal: any, idx: number) => (
          <div key={idx} className="card" style={{ marginLeft: '0', marginTop: '12px' }}>
            <div className="grid">
              <div className="metric">
                <label>Tool</label>
                <div style={{ fontSize: '1em' }}>{proposal.tool_name}</div>
              </div>
              <div className="metric">
                <label>Decision</label>
                <div>
                  <span className={`badge ${proposal.decision === 'ALLOW' ? 'success' : 'error'}`}>
                    {proposal.decision}
                  </span>
                </div>
              </div>
              <div className="metric">
                <label>Effect Type</label>
                <div style={{ fontSize: '1em' }}>{proposal.effect_type}</div>
              </div>
              <div className="metric">
                <label>Status</label>
                <div>
                  <span className={`badge ${proposal.outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                    {proposal.outcome}
                  </span>
                </div>
              </div>
            </div>
            <p><strong>Permit ID:</strong> {proposal.permit_id}</p>
            <p><strong>Request ID:</strong> {proposal.request_id}</p>
            <p><strong>Rationale:</strong> {proposal.rationale}</p>
            {proposal.result && (
              <div>
                <p><strong>Result:</strong></p>
                <p style={{ color: 'rgba(255, 255, 255, 0.8)' }}>{proposal.result}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Provider Receipt (Bedrock)</h2>
        {providerReceipt && (
          <div className="grid">
            <div className="metric">
              <label>Status</label>
              <div>
                <span className={`badge ${providerReceipt.execution_outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                  {providerReceipt.execution_outcome}
                </span>
              </div>
            </div>
            <div className="metric">
              <label>Decision</label>
              <div>
                <span className={`badge ${providerReceipt.decision === 'ALLOW' ? 'success' : 'error'}`}>
                  {providerReceipt.decision}
                </span>
              </div>
            </div>
            <div className="metric">
              <label>Cost (USD)</label>
              <div style={{ fontSize: '1.5em', fontWeight: '600' }}>${providerReceipt.cost_usd.toFixed(2)}</div>
            </div>
            <div className="metric">
              <label>Duration (ms)</label>
              <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{providerReceipt.duration_ms}</div>
            </div>
            <div className="metric">
              <label>Input Tokens</label>
              <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{providerReceipt.usage?.input_tokens || 0}</div>
            </div>
            <div className="metric">
              <label>Output Tokens</label>
              <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{providerReceipt.usage?.output_tokens || 0}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Sandbox Receipt</h2>
        {sandboxReceipt && (
          <div>
            <div className="grid">
              <div className="metric">
                <label>Status</label>
                <div>
                  <span className={`badge ${sandboxReceipt.status === 'SUCCESS' ? 'success' : 'error'}`}>
                    {sandboxReceipt.status}
                  </span>
                </div>
              </div>
              <div className="metric">
                <label>Profile</label>
                <div style={{ fontSize: '1em' }}>{sandboxReceipt.profile}</div>
              </div>
              <div className="metric">
                <label>Capability</label>
                <div style={{ fontSize: '1em' }}>{sandboxReceipt.capability}</div>
              </div>
              <div className="metric">
                <label>Exit Code</label>
                <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{sandboxReceipt.exit_code}</div>
              </div>
              <div className="metric">
                <label>Duration (ms)</label>
                <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{sandboxReceipt.duration_ms}</div>
              </div>
              <div className="metric">
                <label>Network</label>
                <div style={{ fontSize: '1em' }}>{sandboxReceipt.network_mode}</div>
              </div>
            </div>
            <p><strong>Sandbox ID:</strong> {sandboxReceipt.sandbox_id}</p>
            <p><strong>Permit ID:</strong> {sandboxReceipt.permit_id}</p>
          </div>
        )}
      </div>
    </div>
  )
}
