import './CatalogQuality.css'
import { useEffect, useState } from 'react'

type ServiceStatus = { state?: 'healthy' | 'unavailable'; configured?: boolean; healthy?: boolean; service_kind?: string }
type Check = { name?: string; status?: string; detail?: string; receipt?: Record<string, unknown>; receipt_id?: string }
type Validation = { run_id?: string; status?: string; checks?: Check[]; receipts?: Array<Record<string, unknown>>; cleanup_status?: string; cleanup_requested?: boolean; error?: string | null; service_kind?: string }

async function errorMessage(response: Response) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') return body.detail
    if (typeof body?.detail?.message === 'string') return body.detail.message
  } catch { /* status is enough */ }
  if (response.status === 404 || response.status === 405) return 'La validación de catálogo local no está disponible en este backend.'
  return `La solicitud falló (${response.status}).`
}

function display(value: unknown) {
  if (value === undefined || value === null || value === '') return 'No disponible en la respuesta del backend'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export default function CatalogQuality() {
  const [service, setService] = useState<ServiceStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Validation | null>(null)

  useEffect(() => {
    let active = true
    void fetch('/api/catalog/openmetadata/status').then(async response => {
      if (!response.ok) throw new Error(await errorMessage(response))
      return response.json() as Promise<ServiceStatus>
    }).then(body => { if (active) setService(body) })
      .catch(cause => { if (active) setStatusError(cause instanceof Error ? cause.message : 'No se pudo consultar el estado del catálogo local.') })
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
      if (!response.ok) throw new Error(await errorMessage(response))
      const body = await response.json() as Validation
      if (!body || typeof body.status !== 'string' || !Array.isArray(body.checks) || !Array.isArray(body.receipts)
        || typeof body.cleanup_status !== 'string' || typeof body.run_id !== 'string' || typeof body.cleanup_requested !== 'boolean') {
        throw new Error('El backend devolvió un registro incompleto. No se presenta como resultado verificado.')
      }
      setResult(body)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Falló la validación del catálogo local.') }
    finally { setLoading(false) }
  }

  const available = service?.configured === true && service?.healthy === true && service?.state === 'healthy'
  return <section className="catalog-quality" aria-labelledby="catalog-quality-title">
    <header><p className="section-eyebrow">OpenMetadata · catálogo local</p><h2 id="catalog-quality-title">Comprobar catálogo y calidad</h2>
      <p>La comprobación crea entidades temporales de prueba, comprueba búsqueda, lineage, propietario, versión de esquema y definición de regla de calidad, y elimina sus propios recursos.</p></header>
    <p className="catalog-quality-limit"><strong>Alcance:</strong> solo servicio OpenMetadata local de loopback y activos temporales de prueba. La definición de regla no inicia un análisis continuo ni valida activos de producción.</p>
    {statusLoading && <p role="status">Consultando disponibilidad del servicio local…</p>}
    {!statusLoading && statusError && <p className="catalog-quality-error" role="alert">Estado del servicio no disponible: {statusError}</p>}
    {!statusLoading && !statusError && <p className={`catalog-quality-service ${available ? 'is-available' : ''}`} role="status"><strong>{available ? 'Servicio local configurado y saludable' : service?.configured ? 'Servicio local configurado, pero no saludable' : 'Servicio local no configurado o no disponible'}</strong>{service?.service_kind ? ` · ${service.service_kind}` : ''}{service?.state ? ` · ${service.state}` : ''}</p>}
    <div className="catalog-quality-confirm"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={loading} /> Confirmo ejecutar la validación contra el catálogo temporal local. Creará y borrará entidades de prueba.</label>
      <button type="button" onClick={() => void run()} disabled={!confirmed || loading || statusLoading || !available}>{loading ? 'Ejecutando comprobaciones…' : 'Run local OpenMetadata catalog check'}</button></div>
    {loading && <p role="status">Ejecutando las comprobaciones solicitadas; esperando también el resultado de limpieza.</p>}
    {error && <p className="catalog-quality-error" role="alert">{error}</p>}
    {result && <section className="catalog-quality-result" aria-label="Resultado de la validación del catálogo">
      <h3>Resultado devuelto por el backend: {result.status}</h3>
      <dl><div><dt>Run ID</dt><dd><code>{display(result.run_id)}</code></dd></div><div><dt>Servicio</dt><dd>{display(result.service_kind)}</dd></div><div><dt>Limpieza solicitada</dt><dd>{String(result.cleanup_requested)}</dd></div><div><dt>Estado de limpieza</dt><dd className={result.cleanup_status === 'PASS' ? 'catalog-pass' : 'catalog-fail'}>{result.cleanup_status}</dd></div></dl>
      {result.cleanup_status !== 'PASS' && <p className="catalog-quality-error" role="alert">La limpieza no quedó confirmada como PASS. El resultado global requiere revisión.</p>}
      <h4>Comprobaciones</h4><ul className="catalog-quality-checks">{result.checks!.map((check, index) => <li key={`${check.name ?? 'check'}-${index}`}><h5>{display(check.name)}</h5><p>Estado: <strong>{display(check.status)}</strong></p><p>{display(check.detail)}</p>{check.receipt && <pre>{JSON.stringify(check.receipt, null, 2)}</pre>}{check.receipt_id && <p>Receipt ID: <code>{check.receipt_id}</code></p>}</li>)}</ul>
      <h4>Recibos devueltos</h4>{result.receipts!.length ? <ul className="catalog-quality-receipts">{result.receipts!.map((receipt, index) => <li key={`${String(receipt.receipt_id ?? receipt.id ?? 'receipt')}-${index}`}><p>{display(receipt.label)} · {display(receipt.operation)}</p><p>Receipt ID: <code>{display(receipt.receipt_id)}</code></p><p>Decisión / resultado: {display(receipt.decision)} / {display(receipt.outcome)}</p><p>Resultados: {display(receipt.result_count)} · Error: {display(receipt.error_kind)} · Path: {display(receipt.path)}</p></li>)}</ul> : <p>No hay recibos en la respuesta del backend.</p>}
      {result.error && <p className="catalog-quality-error" role="alert">Mensaje del backend: {result.error}</p>}
      <p>La comprobación de denegación debe devolver <code>REQUIRE_HUMAN</code> antes del transporte; se muestra exactamente el resultado recibido.</p>
    </section>}
  </section>
}
