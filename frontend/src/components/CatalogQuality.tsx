import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './CatalogQuality.css'
import { useEffect, useState } from 'react'

type ServiceStatus = { state?: 'healthy' | 'unavailable'; configured?: boolean; healthy?: boolean; service_kind?: string }
type Check = { name?: string; status?: string; detail?: string; receipt?: Record<string, unknown>; receipt_id?: string }
type Validation = { run_id?: string; status?: string; checks?: Check[]; receipts?: Array<Record<string, unknown>>; cleanup_status?: string; cleanup_requested?: boolean; error?: string | null; service_kind?: string }

async function requestError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null)
  if ((response.status === 404 || response.status === 405) && !(typeof body?.detail === 'string' || typeof body?.detail?.message === 'string')) return localMessage('core.CatalogQuality.local_catalog_validation_is_not_supported_by_f3fbd0')
  return apiError(body,response.status,'agents')
}

function display(value: unknown) {
  if (value === undefined || value === null || value === '') return t("core.CatalogQuality.not_available_in_the_backend_response_48f83f")
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export default function CatalogQuality() {
  useI18n()

  const [service, setService] = useState<ServiceStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState<any>('')
  const [confirmed, setConfirmed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<any>('')
  const [result, setResult] = useState<Validation | null>(null)

  useEffect(() => {
    let active = true
    void fetch('/api/catalog/openmetadata/status').then(async response => {
      if (!response.ok) throw await requestError(response)
      return response.json() as Promise<ServiceStatus>
    }).then(body => { if (active) setService(body) })
      .catch(cause => { if (active) setStatusError(cause instanceof Error ? cause : localMessage('agents.aux.CatalogQuality.no_se_pudo_consultar_el_estado_del_catalogo_local')) })
      .finally(() => { if (active) setStatusLoading(false) })
    return () => { active = false }
  }, [])

  const run = async () => {
    if (!confirmed || loading) return
    setLoading(true); setError(''); setResult(null)
    try {
      const response = await fetch('/api/catalog/openmetadata/live-validation', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm_run: true }),
      })
      if (!response.ok) throw await requestError(response)
      const body = await response.json() as Validation
      if (!body || typeof body.status !== 'string' || !Array.isArray(body.checks) || !Array.isArray(body.receipts)
        || typeof body.cleanup_status !== 'string' || typeof body.run_id !== 'string' || typeof body.cleanup_requested !== 'boolean') {
        throw localMessage("core.CatalogQuality.the_backend_returned_an_incomplete_record_it_139aa3")
      }
      setResult(body)
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.CatalogQuality.fallo_la_validacion_del_catalogo_local')) }
    finally { setLoading(false) }
  }

  const available = service?.configured === true && service?.healthy === true && service?.state === 'healthy'
  return <section className="catalog-quality" aria-labelledby="catalog-quality-title">
    <header><p className="section-eyebrow">{t("core.CatalogQuality.openmetadata_local_catalog_e4269c")}</p><h2 id="catalog-quality-title">{t("core.CatalogQuality.check_catalog_and_quality_9bd7cb")}</h2>
      <p>{t("core.CatalogQuality.the_check_creates_temporary_test_entities_checks_432e96")}</p></header>
    <p className="catalog-quality-limit"><strong>{t("core.CatalogQuality.scope_f520f4")}</strong>{' '}{t("core.CatalogQuality.local_loopback_openmetadata_service_and_temporary_test_185e94")}</p>
    {statusLoading && <p role="status">{t("core.CatalogQuality.checking_local_service_availability_f99b88")}</p>}
    {!statusLoading && statusError && <p className="catalog-quality-error" role="alert">{t("core.CatalogQuality.service_status_unavailable_95329b")}{' '}{errorMessage(statusError)}</p>}
    {!statusLoading && !statusError && <p className={`catalog-quality-service ${available ? 'is-available' : ''}`} role="status"><strong>{available ? t("core.CatalogQuality.local_service_configured_and_healthy_bd7656") : service?.configured ? t("core.CatalogQuality.local_service_configured_but_unhealthy_c8e429") : t("core.CatalogQuality.local_service_not_configured_or_unavailable_d73a09")}</strong>{service?.service_kind ? ` · ${service.service_kind}` : ''}{service?.state ? ` · ${observedStateLabel(service.state)}` : ''}</p>}
    <div className="catalog-quality-confirm"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={loading} />{' '}{t("core.CatalogQuality.i_confirm_running_validation_against_the_temporary_99bea8")}</label>
      <button type="button" onClick={() => void run()} disabled={!confirmed || loading || statusLoading || !available}>{loading ? t("core.CatalogQuality.running_checks_7b5de3") : t("core.CatalogQuality.run_local_openmetadata_catalog_check_df3d45")}</button></div>
    {loading && <p role="status">{t("core.CatalogQuality.running_the_requested_checks_and_waiting_for_16d942")}</p>}
    {error && <p className="catalog-quality-error" role="alert">{errorMessage(error)}</p>}
    {result && <section className="catalog-quality-result" aria-label={t("core.CatalogQuality.catalog_validation_result_cee403")}>
      <h3>{t("core.CatalogQuality.result_returned_by_the_backend_130859")}{' '}{observedStateLabel(result.status)}</h3>
      <dl><div><dt>{t("core.CatalogQuality.run_id_26d3e7")}</dt><dd><code>{display(result.run_id)}</code></dd></div><div><dt>{t("core.CatalogQuality.service_1efa3b")}</dt><dd>{display(result.service_kind)}</dd></div><div><dt>{t("core.CatalogQuality.cleanup_requested_323e9f")}</dt><dd>{result.cleanup_requested ? t('agents.aux.ExternalConnections.si') : t('agents.aux.ExternalConnections.no')}</dd></div><div><dt>{t("core.CatalogQuality.cleanup_status_13cba7")}</dt><dd className={result.cleanup_status === 'PASS' ? 'catalog-pass' : 'catalog-fail'}>{result.cleanup_status}</dd></div></dl>
      {result.cleanup_status !== 'PASS' && <p className="catalog-quality-error" role="alert">{t("core.CatalogQuality.cleanup_was_not_confirmed_as_pass_the_5e8eb4")}</p>}
      <h4>{t("core.CatalogQuality.checks_d3b4f1")}</h4><ul className="catalog-quality-checks">{result.checks!.map((check, index) => <li key={`${check.name ?? 'check'}-${index}`}><h5>{display(check.name)}</h5><p>{t("core.CatalogQuality.status_5e194f")}{' '}<strong>{display(check.status)}</strong></p><p>{display(check.detail)}</p>{check.receipt && <pre>{JSON.stringify(check.receipt, null, 2)}</pre>}{check.receipt_id && <p>{t("core.CatalogQuality.receipt_id_9ba800")}{' '}<code>{check.receipt_id}</code></p>}</li>)}</ul>
      <h4>{t("core.CatalogQuality.returned_receipts_351348")}</h4>{result.receipts!.length ? <ul className="catalog-quality-receipts">{result.receipts!.map((receipt, index) => <li key={`${String(receipt.receipt_id ?? receipt.id ?? 'receipt')}-${index}`}><p>{display(receipt.label)} · {display(receipt.operation)}</p><p>{t("core.CatalogQuality.receipt_id_9ba800")}{' '}<code>{display(receipt.receipt_id)}</code></p><p>{t("core.CatalogQuality.decision_result_fb59b8")}{' '}{display(receipt.decision)} / {display(receipt.outcome)}</p><p>{t("core.CatalogQuality.results_21d53d")}{' '}{display(receipt.result_count)}{' '}{t("core.CatalogQuality.error_e114d7")}{' '}{display(receipt.error_kind)}{' '}{t("core.CatalogQuality.path_9bfb7d")}{' '}{display(receipt.path)}</p></li>)}</ul> : <p>{t("core.CatalogQuality.there_are_no_receipts_in_the_backend_8676c8")}</p>}
      {result.error && <p className="catalog-quality-error" role="alert">{t("core.CatalogQuality.backend_message_df9859")}{' '}{result.error}</p>}
      <p>{t("core.CatalogQuality.the_denial_check_must_return_0ae66a")}{' '}<code>REQUIRE_HUMAN</code>{' '}{t("core.CatalogQuality.before_transport_the_exact_returned_result_is_7894d6")}</p>
    </section>}
  </section>
}

/** Presentation only: preserve the exact observed protocol value alongside its label. */
function observedStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
"running":()=>t('agents.aux.state.running'),
"success":()=>t('agents.aux.state.success'),
"failed":()=>t('agents.aux.state.failed'),
"timeout":()=>t('agents.aux.state.timeout'),
"demo":()=>t('agents.aux.state.demo'),
"agent":()=>t('agents.aux.state.agent'),
"PROPOSED":()=>t('agents.aux.state.PROPOSED'),
"VERIFIED":()=>t('agents.aux.state.VERIFIED'),
"PENDING_REVIEW":()=>t('agents.aux.state.PENDING_REVIEW'),
"CANCELLED":()=>t('agents.aux.state.CANCELLED'),
"EXPIRED":()=>t('agents.aux.state.EXPIRED'),
"AVAILABLE":()=>t('agents.aux.state.AVAILABLE'),
"UNAVAILABLE":()=>t('agents.aux.state.UNAVAILABLE'),
"READY":()=>t('agents.aux.state.READY'),
"NOT_READY":()=>t('agents.aux.state.NOT_READY'),
"AWAITING_APPROVAL":()=>t('agents.aux.state.AWAITING_APPROVAL'),
"APPROVED":()=>t('agents.aux.state.APPROVED'),
"REJECTED":()=>t('agents.aux.state.REJECTED'),
"SUCCEEDED":()=>t('agents.aux.state.SUCCEEDED'),
"FAILED":()=>t('agents.aux.state.FAILED'),
"REVOKED":()=>t('agents.aux.state.REVOKED'),
"UNKNOWN":()=>t('agents.aux.state.UNKNOWN'),
"PASS":()=>t('agents.aux.state.PASS'),
"FAIL":()=>t('agents.aux.state.FAIL'),
"ERROR":()=>t('agents.aux.state.ERROR'),
"healthy":()=>t('agents.aux.state.healthy'),
"unavailable":()=>t('agents.aux.state.unavailable'),
"ALLOW":()=>t('agents.aux.state.ALLOW'),
"DENY":()=>t('agents.aux.state.DENY'),
"REQUIRE_HUMAN":()=>t('agents.aux.state.REQUIRE_HUMAN'),
"SUCCESS":()=>t('agents.aux.state.SUCCESS'),
"DENIED":()=>t('agents.aux.state.DENIED'),
"configured":()=>t('agents.aux.state.configured'),
"connected":()=>t('agents.aux.state.connected'),
"present":()=>t('agents.aux.state.present'),
"absent":()=>t('agents.aux.state.absent')
  }
  return Object.prototype.hasOwnProperty.call(labels,value) ? `${labels[value]()} (${value})` : t('agents.aux.state.unknownCode',{value})
}
