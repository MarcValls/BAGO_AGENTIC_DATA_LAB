import './Retrieval.css'

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

export default function Retrieval({ data }: Props) {
  const retrieval = data.agent_run.retrieval || {}
  const ontology = data.agent_run.ontology || {}

  return (
    <div>
      <div className="card">
        <h2>Retrieval Pipeline</h2>
        <div className="grid">
          <div className="metric">
            <label>Hits</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{retrieval.eligible_count || 0}</div>
          </div>
          <div className="metric">
            <label>Filtered</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{retrieval.filtered_count || 0}</div>
          </div>
          <div className="metric">
            <label>Mode</label>
            <div style={{ fontSize: '1em' }}>{retrieval.mode}</div>
          </div>
        </div>

        <h3>Pipeline Steps</h3>
        <div className="timeline">
          {(retrieval.pipeline || []).map((step: string, idx: number) => (
            <div key={idx} className="timeline-item success">
              <strong>{step}</strong>
            </div>
          ))}
        </div>

        <h3>Retrieved Documents</h3>
        <div>
          {(retrieval.hits || []).map((hit: any, idx: number) => (
            <div key={idx} className="card" style={{ marginLeft: '0', marginTop: '12px' }}>
              <div className="grid">
                <div className="metric">
                  <label>Rank</label>
                  <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{hit.rank}</div>
                </div>
                <div className="metric">
                  <label>Score</label>
                  <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{hit.score.toFixed(3)}</div>
                </div>
                <div className="metric">
                  <label>Lexical</label>
                  <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{hit.lexical_score.toFixed(3)}</div>
                </div>
                <div className="metric">
                  <label>Semantic</label>
                  <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{hit.semantic_score.toFixed(3)}</div>
                </div>
              </div>
              <p><strong>Document:</strong> {hit.document_id}</p>
              <p><strong>Chunk:</strong> {hit.chunk_id}</p>
              <p><strong>Citation:</strong> {hit.evidence?.citation}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Ontology Engine (RDF/SPARQL)</h2>
        <div className="grid">
          <div className="metric">
            <label>Paths Found</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{ontology.paths?.length || 0}</div>
          </div>
          <div className="metric">
            <label>Inferred Triples</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{ontology.inferred_triples?.length || 0}</div>
          </div>
          <div className="metric">
            <label>Contradictions</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>{ontology.receipt?.contradictions_found || 0}</div>
          </div>
          <div className="metric">
            <label>Status</label>
            <div style={{ fontSize: '1.5em', fontWeight: '600' }}>
              <span className={`badge ${ontology.receipt?.outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                {ontology.receipt?.outcome}
              </span>
            </div>
          </div>
        </div>

        <h3>Ontology Paths</h3>
        <div>
          {(ontology.paths || []).map((path: any, idx: number) => (
            <div key={idx} style={{ marginBottom: '16px' }}>
              <div className="graph">
                {(path.nodes || []).map((node: string, nidx: number) => (
                  <span key={nidx}>
                    {nidx > 0 && <span className="path-arrow">→</span>}
                    <span className="path-node">{node.split('/').pop()}</span>
                  </span>
                ))}
              </div>
              {path.triples && path.triples.length > 0 && (
                <details style={{ marginTop: '8px' }}>
                  <summary>Triples ({path.triples.length})</summary>
                  <div style={{ marginTop: '8px' }}>
                    {path.triples.map((triple: any, tidx: number) => (
                      <div key={tidx} style={{ fontSize: '0.85em', marginBottom: '4px' }}>
                        <strong>{triple.subject.split('/').pop()}</strong>
                        {' '}<em>{triple.predicate.split('/').pop()}</em>{' '}
                        <strong>{triple.object.split('/').pop()}</strong>
                        {triple.inferred && <span style={{ color: '#fbbf24' }}> [inferred]</span>}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>

        <h3>SPARQL Queries</h3>
        <div>
          {(ontology.sparql_queries || []).map((query: string, idx: number) => (
            <div key={idx} className="json-panel" style={{ marginBottom: '8px' }}>
              {query}
            </div>
          ))}
        </div>

        <h3>Evidence</h3>
        <ul className="evidence-list">
          {(ontology.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
