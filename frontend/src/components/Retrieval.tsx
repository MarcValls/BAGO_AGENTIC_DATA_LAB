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
            <div>{retrieval.eligible_count || 0}</div>
          </div>
          <div className="metric">
            <label>Filtered</label>
            <div>{retrieval.filtered_count || 0}</div>
          </div>
          <div className="metric">
            <label>Mode</label>
            <div>{retrieval.mode}</div>
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
            <div key={idx} className="card">
              <div className="grid">
                <div className="metric">
                  <label>Rank</label>
                  <div>{hit.rank}</div>
                </div>
                <div className="metric">
                  <label>Score</label>
                  <div>{hit.score.toFixed(3)}</div>
                </div>
                <div className="metric">
                  <label>Lexical</label>
                  <div>{hit.lexical_score.toFixed(3)}</div>
                </div>
                <div className="metric">
                  <label>Semantic</label>
                  <div>{hit.semantic_score.toFixed(3)}</div>
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
            <div>{ontology.paths?.length || 0}</div>
          </div>
          <div className="metric">
            <label>Inferred Triples</label>
            <div>{ontology.inferred_triples?.length || 0}</div>
          </div>
          <div className="metric">
            <label>Contradictions</label>
            <div>{ontology.receipt?.contradictions_found || 0}</div>
          </div>
          <div className="metric">
            <label>Status</label>
            <div>
              <span className={`badge ${ontology.receipt?.outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                {ontology.receipt?.outcome}
              </span>
            </div>
          </div>
        </div>

        <h3>Ontology Paths</h3>
        <div>
          {(ontology.paths || []).map((path: any, idx: number) => (
            <div key={idx}>
              <div className="graph">
                {(path.nodes || []).map((node: string, nidx: number) => (
                  <span key={nidx}>
                    {nidx > 0 && <span className="path-arrow">→</span>}
                    <span className="path-node">{node.split('/').pop()}</span>
                  </span>
                ))}
              </div>
              {path.triples && path.triples.length > 0 && (
                <details>
                  <summary>Triples ({path.triples.length})</summary>
                  <div>
                    {path.triples.map((triple: any, tidx: number) => (
                      <div key={tidx}>
                        <strong>{triple.subject.split('/').pop()}</strong>
                        {' '}<em>{triple.predicate.split('/').pop()}</em>{' '}
                        <strong>{triple.object.split('/').pop()}</strong>
                        {triple.inferred && <span> [inferred]</span>}
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
            <div key={idx} className="json-panel">
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
