// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react'
import JobHistory, {type WorkHistoryItem} from '../../src/components/JobHistory'
import {formatDate, formatNumber, resetLocaleForTests, setLocale} from '../../src/i18n'

beforeEach(() => {localStorage.clear(); resetLocaleForTests(); setLocale('es')})
afterEach(() => {cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks()})
const kinds = ['legacy_job', 'task_run', 'delegation', 'agent_turn', 'evaluation'] as const
const item = (kind: WorkHistoryItem['kind'] = 'task_run', id = 'own', overrides: Partial<WorkHistoryItem> = {}): WorkHistoryItem => ({
  key: `${kind}:${id}`, kind, id, status: 'failed', agent_id: 'deleted-agent-id', agent_name: null,
  parent_conversation_id: 'parent-opaque', conversation_id: 'conversation-opaque', message_id: 'message-opaque',
  trace_id: 'EXACT-OPAQUE-TRACE', receipt_id: 'EXACT-OPAQUE-RECEIPT', receipt_sha256: 'a'.repeat(64),
  created_at: '2026-10-24T12:34:56Z', started_at: null, completed_at: null, activity_at: '2026-10-25T12:34:56Z',
  duration_ms: 0, cost_usd: 0, tools_executed: false, target_written: false, tool_receipt_count: 0, related_key: null, ...overrides,
})
const sources = () => kinds.map(kind => ({kind, state: 'available', error_code: null, truncated: false}))
const page = (items = [item()], overrides: Record<string, unknown> = {}) => ({schema: 'work-history.v1', items, total: items.length, limit: 50, offset: 0, has_more: false, next_offset: null, sources: sources(), ...overrides})
const response = (data: unknown, status = 200) => ({ok: status < 400, status, json: vi.fn(async () => data)})
type Call = {url: string; init?: RequestInit}
function setup(handler: (url: string, index: number) => unknown | Promise<unknown> = () => response(page()), onSelect = vi.fn(), inline = false) {
  const calls: Call[] = []
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {calls.push({url, init}); return await handler(url, calls.length - 1)})
  vi.stubGlobal('fetch', fetcher)
  const view = render(<JobHistory inline={inline} onJobSelect={onSelect}/>)
  return {calls, fetcher, onSelect, view}
}
const row = (key = 'task_run:own') => screen.getByRole('button', {name: new RegExp(key)})
const findRow = (key = 'task_run:own') => screen.findByRole('button', {name: new RegExp(key)})
const details = () => screen.getByRole('region', {name: 'Metadatos del registro'})
const detailValue = (label: string) => within(details()).getByText(label, {selector: 'dt'}).nextElementSibling!
function deferred<T>() {let resolve!: (value: T) => void; const promise = new Promise<T>(r => {resolve = r}); return {promise, resolve}}

it('loads five sources and distinct attempts with one metadata request; selection exposes no bodies or execution', async () => {
  const records = kinds.map((kind, index) => item(kind, 'shared', {status: ['success', 'failed', 'PASSED', 'answered', 'EXACT-STATE'][index]}))
  const leaked = {...records[0], content: 'PRIVATE BODY MARKER', stdout: 'PRIVATE STDOUT MARKER', workspace_path: 'PRIVATE PATH MARKER', grants: ['PRIVATE GRANT MARKER']}
  const f = setup(() => response(page([leaked, ...records.slice(1)])))
  await findRow('legacy_job:shared')
  expect(f.calls.map(c => c.url)).toEqual(['/api/work-history?limit=50&offset=0&kind=all'])
  expect(f.view.container.querySelectorAll('.work-history-row')).toHaveLength(5)
  expect(f.view.container.querySelectorAll('.work-history-sources li')).toHaveLength(5)
  for (const record of records) expect(row(record.key)).toBeTruthy()
  fireEvent.click(row('legacy_job:shared'))
  expect(f.onSelect).toHaveBeenCalledExactlyOnceWith(records[0])
  expect(f.view.container.textContent).not.toMatch(/PRIVATE (BODY|STDOUT|PATH|GRANT) MARKER/)
  expect(detailValue('ID de traza').textContent).toBe('EXACT-OPAQUE-TRACE')
  expect(detailValue('ID de recibo').textContent).toBe('EXACT-OPAQUE-RECEIPT')
  expect(f.calls).toHaveLength(1)
  expect(f.calls[0].init?.method).toBeUndefined()
  expect(f.view.container.querySelector('a[href*="trace"]')).toBeNull()
})

it.each(['PASSED', 'answered'])('labels %s as received response and keeps false effects visible without claiming task completion', async status => {
  const f = setup(() => response(page([item('delegation', 'response', {status})])))
  fireEvent.click(await findRow('delegation:response'))
  expect(row('delegation:response').textContent).toContain('Respuesta recibida')
  expect(row('delegation:response').textContent).toContain(status)
  expect(detailValue('Herramientas ejecutadas').textContent).toBe('No')
  expect(detailValue('Escritura registrada').textContent).toBe('No')
  expect(f.view.container.textContent).not.toMatch(/Tarea completada|traza verificada|ejecución verificada/i)
})

it('preserves unknown versus zero, false and true values, and displays explicit UTC dates', async () => {
  const f = setup(() => response(page([item(), item('evaluation', 'unknown', {status: null, duration_ms: null, cost_usd: null, tools_executed: null, target_written: null, tool_receipt_count: null, activity_at: 'invalid'}), item('agent_turn', 'effects', {tools_executed: true, target_written: true})])))
  fireEvent.click(await findRow())
  expect(detailValue('Duración').textContent).toBe('0 ms')
  expect(detailValue('Coste').textContent).toBe('$' + formatNumber(0, {minimumFractionDigits: 4, maximumFractionDigits: 4}))
  expect(detailValue('Recibos de herramienta').textContent).toBe('0')
  expect(detailValue('Creación').textContent).toBe(formatDate('2026-10-24T12:34:56Z') + ' UTC')
  expect(f.view.container.querySelector('time')?.getAttribute('dateTime')).toBe('2026-10-25T12:34:56Z')
  fireEvent.click(row('evaluation:unknown'))
  for (const label of ['Duración', 'Coste', 'Herramientas ejecutadas', 'Escritura registrada', 'Recibos de herramienta']) expect(detailValue(label).textContent).toBe('No registrado')
  expect(row('evaluation:unknown').textContent).toContain('Fecha no disponible')
  expect(row('evaluation:unknown').textContent).toContain('Estado no registrado')
  fireEvent.click(row('agent_turn:effects'))
  expect(detailValue('Herramientas ejecutadas').textContent).toBe('Sí')
  expect(detailValue('Escritura registrada').textContent).toBe('Sí')
})

it('retains server ordering, repeated agent attempts and explicit related records without deduplication', async () => {
  const records = [item('agent_turn', 'z', {related_key: 'delegation:a'}), item('delegation', 'a', {status: 'PASSED', related_key: 'agent_turn:z'}), item('task_run', 'a', {activity_at: null})]
  const f = setup(() => response(page(records)))
  await findRow('agent_turn:z')
  expect(Array.from(f.view.container.querySelectorAll('.work-history-key')).map(el => el.textContent)).toEqual(records.map(record => record.key))
  fireEvent.click(row('agent_turn:z'))
  expect(detailValue('Registro relacionado').textContent).toBe('delegation:a')
  expect(f.calls).toHaveLength(1)
})

it('filters every source on the server, pages with the returned cursor, and refreshes the current query manually', async () => {
  const f = setup(url => {const q = new URL(url, 'https://fixture.test').searchParams; const kind = q.get('kind')!, offset = Number(q.get('offset')); return response(page([item(kind === 'all' ? 'task_run' : kind as WorkHistoryItem['kind'], 'page-' + offset)], {offset, total: 80, has_more: offset === 0, next_offset: offset === 0 ? 50 : null}))})
  await findRow('task_run:page-0')
  const next = screen.getByRole('button', {name: 'Siguiente'})
  next.focus(); fireEvent.click(next)
  await findRow('task_run:page-50')
  expect(document.activeElement).toBe(next)
  expect(next.getAttribute('aria-disabled')).toBe('true')
  expect(f.calls[1].url).toBe('/api/work-history?limit=50&offset=50&kind=all')
  const refresh = screen.getByRole('button', {name: 'Actualizar'})
  refresh.focus(); fireEvent.click(refresh)
  await waitFor(() => expect(refresh.getAttribute('aria-disabled')).toBe('false'))
  expect(f.calls[2].url).toBe(f.calls[1].url)
  expect(document.activeElement).toBe(refresh)
  for (const kind of kinds) {
    fireEvent.change(screen.getByLabelText('Filtrar por fuente'), {target: {value: kind}})
    await findRow(`${kind}:page-0`)
    expect(f.calls.at(-1)!.url).toBe(`/api/work-history?limit=50&offset=0&kind=${kind}`)
  }
  fireEvent.click(screen.getByRole('button', {name: 'Siguiente'})); await findRow('evaluation:page-50')
  fireEvent.click(screen.getByRole('button', {name: 'Anterior'})); await findRow('evaluation:page-0')
  expect(f.calls.at(-1)!.url).toBe('/api/work-history?limit=50&offset=0&kind=evaluation')
})

it.each(['available', 'absent'])('distinguishes a successful empty %s source from an error', async state => {
  setup(() => response(page([], {sources: sources().map(s => ({...s, state}))})))
  await screen.findByText('No hay registros en esta selección.')
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.queryByText(/cobertura es incompleta/)).toBeNull()
})
it.each(['partial', 'unavailable'])('shows %s coverage honestly for empty and populated results', async state => {
  const f = setup((_url, index) => response(page(index === 0 ? [] : [item()], {sources: sources().map((s, i) => i ? s : {...s, state, truncated: true, error_code: 'SAFE_CODE'})})))
  await screen.findByText('No hay registros enumerados en esta selección; la cobertura es incompleta.')
  expect(screen.getByText('SAFE_CODE')).toBeTruthy()
  expect(f.view.container.querySelector('details')?.open).toBe(true)
  fireEvent.click(screen.getByRole('button', {name: 'Actualizar'})); await findRow()
  expect(screen.getByText(/Alguna fuente no está disponible/)).toBeTruthy()
})

it.each([403, 500])('shows HTTP %s as an error without reading raw diagnostics or a false empty state', async status => {
  const failed = response({detail: 'PRIVATE RAW ERROR'}, status)
  setup(() => failed)
  expect((await screen.findByRole('alert')).textContent).toContain('HTTP ' + status)
  expect(screen.queryByText('No hay registros en esta selección.')).toBeNull()
  expect(screen.queryByText('PRIVATE RAW ERROR')).toBeNull()
  expect(failed.json).not.toHaveBeenCalled()
})
it('shows network failures and supports an explicit successful retry', async () => {
  const f = setup((_url, index) => {if (!index) throw new Error('PRIVATE TRANSPORT ERROR'); return response(page())})
  await screen.findByRole('alert')
  expect(f.view.container.textContent).not.toContain('PRIVATE TRANSPORT ERROR')
  fireEvent.click(screen.getByRole('button', {name: 'Actualizar'})); await findRow()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(f.calls).toHaveLength(2)
})
it('reports invalid JSON as an incompatible response without a false empty state', async () => {
  setup(() => ({ok: true, status: 200, json: async () => {throw new Error('PRIVATE JSON ERROR')}}))
  expect((await screen.findByRole('alert')).textContent).toContain('índice de historial compatible')
  expect(screen.queryByText('PRIVATE JSON ERROR')).toBeNull()
  expect(screen.queryByText('No hay registros en esta selección.')).toBeNull()
})
it('rejects a server response for the wrong requested source without showing old records as current', async () => {
  setup(() => response(page()))
  await findRow()
  fireEvent.change(screen.getByLabelText('Filtrar por fuente'), {target: {value: 'evaluation'}})
  await screen.findByRole('alert')
  expect(screen.queryByRole('button', {name: /task_run:own/})).toBeNull()
})
it('offers an explicit return to the first page when records shrink without automatically fetching it', async () => {
  const f = setup((_url, index) => response(index === 0 ? page([item()], {total: 51, has_more: true, next_offset: 50}) : page([], {total: 1, offset: index === 1 ? 50 : 0})))
  await findRow()
  fireEvent.click(screen.getByRole('button', {name: 'Siguiente'}))
  await screen.findByText('0–0 de 1 enumerados')
  expect(f.calls).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', {name: 'Primera página'}))
  await waitFor(() => expect(f.calls).toHaveLength(3))
  expect(f.calls[2].url).toBe('/api/work-history?limit=50&offset=0&kind=all')
})

const malformed = [null, {jobs: []}, page([], {schema: 'future.v2'}), page([], {sources: sources().slice(1)}), page([], {sources: [sources()[0], ...sources().slice(1), sources()[0]]}), page([], {has_more: true, next_offset: null}), page([], {has_more: true, next_offset: 0}), page([item('task_run', 'bad', {cost_usd: -1})]), page([{...item(), tools_executed: undefined} as any]), page([item(), item()])]
it.each(malformed.map((body, i) => [i, body] as const))('rejects malformed/unsupported metadata envelope %s instead of fabricating empty success', async (_i, body) => {
  setup(() => response(body))
  expect((await screen.findByRole('alert')).textContent).toContain('índice de historial compatible')
  expect(screen.queryByText('No hay registros en esta selección.')).toBeNull()
})

it('keeps previous data explicitly stale after a refresh failure, not as an updated result', async () => {
  setup((_url, index) => response(index === 0 ? page() : {}, index === 0 ? 200 : 500))
  fireEvent.click(await findRow())
  fireEvent.click(screen.getByRole('button', {name: 'Actualizar'}))
  await screen.findByRole('alert')
  expect(screen.getByText(/Mostrando la última carga válida/)).toBeTruthy()
  expect(detailValue('ID de traza').textContent).toBe('EXACT-OPAQUE-TRACE')
})
it('aborts a superseded request and ignores its late result, warnings and metadata', async () => {
  const old = deferred<unknown>()
  const f = setup((_url, index) => index === 0 ? old.promise : response(page([item('evaluation', 'new')], {sources: sources()})))
  fireEvent.change(screen.getByLabelText('Filtrar por fuente'), {target: {value: 'evaluation'}})
  await findRow('evaluation:new')
  expect(f.calls[0].init?.signal?.aborted).toBe(true)
  await act(async () => old.resolve(response(page([item('task_run', 'old')], {sources: sources().map(s => ({...s, state: 'unavailable'}))}))))
  expect(screen.queryByRole('button', {name: /task_run:old/})).toBeNull()
  expect(screen.queryByText(/Cobertura incompleta/)).toBeNull()
})
it('aborts on unmount and does not dispatch or select when a late request resolves', async () => {
  const pending = deferred<unknown>(), selected = vi.fn()
  const f = setup(() => pending.promise, selected)
  f.view.unmount()
  expect(f.calls[0].init?.signal?.aborted).toBe(true)
  await act(async () => pending.resolve(response(page())))
  expect(selected).not.toHaveBeenCalled()
  expect(f.calls).toHaveLength(1)
})

it('preserves key-based selection with fresh objects and never selects automatically on refresh or locale change', async () => {
  const f = setup((_url, index) => response(page([item('task_run', 'own', {trace_id: index ? 'REFRESHED-OPAQUE' : 'EXACT-OPAQUE-TRACE'})])))
  fireEvent.click(await findRow())
  const refresh = screen.getByRole('button', {name: 'Actualizar'}); refresh.focus(); fireEvent.click(refresh)
  await screen.findByText('REFRESHED-OPAQUE')
  expect(document.activeElement).toBe(refresh)
  expect(f.onSelect).toHaveBeenCalledTimes(1)
  expect(row().getAttribute('aria-expanded')).toBe('true')
  act(() => setLocale('en'))
  expect(screen.getByRole('region', {name: 'Record metadata'}).textContent).toContain('REFRESHED-OPAQUE')
  expect(f.calls).toHaveLength(2)
  expect(f.onSelect).toHaveBeenCalledTimes(1)
})
it('removes old selection details when the selected key disappears rather than presenting stale metadata', async () => {
  setup((_url, index) => response(page([item('task_run', index ? 'other' : 'own')])))
  fireEvent.click(await findRow())
  fireEvent.click(screen.getByRole('button', {name: 'Actualizar'})); await findRow('task_run:other')
  expect(screen.queryByRole('region', {name: 'Metadatos del registro'})).toBeNull()
  expect(screen.getByText(/El registro seleccionado no está en esta página/)).toBeTruthy()
})
it('supports inline selection and returns focus to the row when closing details without another request', async () => {
  const f = setup(undefined, vi.fn(), true)
  const button = await findRow(); button.focus(); fireEvent.click(button)
  expect(f.view.container.querySelector('.job-history-inline')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', {name: 'Cerrar detalles'}))
  expect(document.activeElement).toBe(button)
  expect(button.getAttribute('aria-expanded')).toBe('false')
  expect(f.calls).toHaveLength(1)
})
it('does not poll after mount and never invents a non-metadata endpoint', async () => {
  const f = setup(); await findRow()
  vi.useFakeTimers()
  await act(async () => {vi.advanceTimersByTime(30000)})
  expect(f.calls).toHaveLength(1)
  expect(f.calls.every(call => call.url.startsWith('/api/work-history?') && !call.init?.method)).toBe(true)
})
