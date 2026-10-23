import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber,stateLabel} from '../i18n'
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
  useI18n()

  const retrieval = data.agent_run.retrieval || {}
  const ontology = data.agent_run.ontology || {}

  return (
    <div>
      <div className="card">
        <h2>{t("core.Retrieval.retrieval_pipeline_4a9ff2")}</h2>
        <div className="grid">
          <div className="metric">
            <label>{t("core.Retrieval.hits_f0dcee")}</label>
            <div>{retrieval.eligible_count || 0}</div>
          </div>
          <div className="metric">
            <label>{t("core.Retrieval.filtered_0ba993")}</label>
            <div>{retrieval.filtered_count || 0}</div>
          </div>
          <div className="metric">
            <label>{t("core.Retrieval.mode_5e23ec")}</label>
            <div>{stateLabel(retrieval.mode)}</div>
          </div>
        </div>

        <h3>{t("core.Retrieval.pipeline_steps_662901")}</h3>
        <div className="timeline">
          {(retrieval.pipeline || []).map((step: string, idx: number) => (
            <div key={idx} className="timeline-item success">
              <strong>{step}</strong>
            </div>
          ))}
        </div>

        <h3>{t("core.Retrieval.retrieved_documents_0a980e")}</h3>
        <div>
          {(retrieval.hits || []).map((hit: any, idx: number) => (
            <div key={idx} className="card">
              <div className="grid">
                <div className="metric">
                  <label>{t("core.Retrieval.rank_a4130d")}</label>
                  <div>{hit.rank}</div>
                </div>
                <div className="metric">
                  <label>{t("core.Retrieval.score_38e5a4")}</label>
                  <div>{formatNumber(hit.score,{minimumFractionDigits:3,maximumFractionDigits:3})}</div>
                </div>
                <div className="metric">
                  <label>{t("core.Retrieval.lexical_e77f54")}</label>
                  <div>{formatNumber(hit.lexical_score,{minimumFractionDigits:3,maximumFractionDigits:3})}</div>
                </div>
                <div className="metric">
                  <label>{t("core.Retrieval.semantic_9c11c9")}</label>
                  <div>{formatNumber(hit.semantic_score,{minimumFractionDigits:3,maximumFractionDigits:3})}</div>
                </div>
              </div>
              <p><strong>{t("core.Retrieval.document_8954d7")}</strong> {hit.document_id}</p>
              <p><strong>{t("core.Retrieval.chunk_96d2e8")}</strong> {hit.chunk_id}</p>
              <p><strong>{t("core.Retrieval.citation_674dc9")}</strong> {hit.evidence?.citation}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>{t("core.Retrieval.ontology_engine_rdf_sparql_e0a95a")}</h2>
        <div className="grid">
          <div className="metric">
            <label>{t("core.Retrieval.paths_found_af5412")}</label>
            <div>{ontology.paths?.length || 0}</div>
          </div>
          <div className="metric">
            <label>{t("core.Retrieval.inferred_triples_46561f")}</label>
            <div>{ontology.inferred_triples?.length || 0}</div>
          </div>
          <div className="metric">
            <label>{t("core.Retrieval.contradictions_c1c93b")}</label>
            <div>{ontology.receipt?.contradictions_found || 0}</div>
          </div>
          <div className="metric">
            <label>{t("core.Retrieval.status_920e41")}</label>
            <div>
              <span className={`badge ${ontology.receipt?.outcome === 'SUCCESS' ? 'success' : 'error'}`}>
                {stateLabel(ontology.receipt?.outcome)}
              </span>
            </div>
          </div>
        </div>

        <h3>{t("core.Retrieval.ontology_paths_a345f9")}</h3>
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
                  <summary>{t("core.presentation.triplesCount",{count:formatNumber(path.triples.length)})}</summary>
                  <div>
                    {path.triples.map((triple: any, tidx: number) => (
                      <div key={tidx}>
                        <strong>{triple.subject.split('/').pop()}</strong>
                        {' '}<em>{triple.predicate.split('/').pop()}</em>{' '}
                        <strong>{triple.object.split('/').pop()}</strong>
                        {triple.inferred && <span>{' '}{t("core.Retrieval.inferred_12d7c7")}</span>}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>

        <h3>{t("core.Retrieval.sparql_queries_138d7c")}</h3>
        <div>
          {(ontology.sparql_queries || []).map((query: string, idx: number) => (
            <div key={idx} className="json-panel">
              {query}
            </div>
          ))}
        </div>

        <h3>{t("core.Retrieval.evidence_03867a")}</h3>
        <ul className="evidence-list">
          {(ontology.evidence_refs || []).map((ref: string, idx: number) => (
            <li key={idx} className="evidence-item">{ref}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
