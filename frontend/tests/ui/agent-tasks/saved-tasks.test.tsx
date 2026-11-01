import {setLocale,t} from '../../../src/i18n'
import {beforeEach as beforeLocaleExpectation} from 'vitest'
beforeLocaleExpectation(() => setLocale('es'))
// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AgentTasks from '../../../src/components/AgentTasks'
import AgentBuilder from '../../../src/components/AgentBuilder'
import { taskError } from '../../../src/components/AgentTaskForm'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })
const task = { prompt: 'Revisa ventas de {{fecha_1}}', dates: [{ key: 'fecha_1', label: 'Entrega', value: '2026-10-20' }] }
const oldRun = { run_id: 'run_old', agent_id: 'one', task_revision: 'old', task_snapshot: structuredClone(task), rendered_prompt: 'Revisa ventas de 2026-10-20', provider_id: 'fixture', model_id: 'fixture', workspace_root: '', source_run_id: null, created_at: '2026-10-19T10:00:00Z', completed_at: '2026-10-19T10:00:01Z', status: 'answered', answer: '<script>alert(1)</script>', error: null }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body })
function server(options: { legacy?: boolean; failSave?: boolean; failTask?: boolean; runs?: typeof oldRun[] } = {}) {
  let current = options.legacy ? null : structuredClone(task)
  let revision = 'revision_1'
  const calls: { url: string; method: string; body: any }[] = []
  const fetch = vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input), method = init?.method || 'GET', body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ url, method, body })
    if (url === '/api/agents/list') return response({ agents: [{ id: 'one', config: { name: 'Uno', description: 'Tarea antigua' } }, { id: 'two', config: { name: 'Dos', description: 'Otro agente' } }] })
    if (url.endsWith('/task-runs?limit=50')) return response({ runs: options.runs || [], count: options.runs?.length || 0 })
    if (url.endsWith('/task') && method === 'GET') return options.failTask ? response({ detail: { message: 'Tareas no disponibles.' } }, 404) : response({ agent_id: url.includes('/one/') ? 'one' : 'two', task: current, revision })
    if (url.endsWith('/task') && method === 'PUT') {
      if (options.failSave) return response({ detail: { code: 'stale_revision', message: 'La tarea cambió. Recarga la tarea guardada.' } }, 409)
      current = structuredClone(body.task); revision = 'revision_2'
      return response({ agent_id: 'one', task: current, revision })
    }
    if (url.endsWith('/task-runs') && method === 'POST') return response({ ...oldRun, run_id: 'run_new', task_revision: revision, task_snapshot: current, source_run_id: body.source_run_id, created_at: '2026-10-20T10:00:00Z', completed_at: '2026-10-20T10:00:01Z' })
    if (url === '/api/providers/chat-models') return response({ models: [] })
    throw Error(`Unexpected ${method} ${url}`)
  })
  vi.stubGlobal('fetch', fetch)
  return { calls, fetch }
}
async function chooseAgent() {
  await screen.findByRole('option', { name: 'Uno' })
  fireEvent.change(screen.getByRole('combobox', { name: t('agents.AgentTasks.agente_para_tareas') }), { target: { value: 'one' } })
  await screen.findByRole('textbox', { name: t('agents.AgentTaskForm.tarea') })
}

it('loads saved task without inference and requires saving changed dates before an explicit run', async () => {
  const { calls } = server()
  render(<AgentTasks />)
  await chooseAgent()
  expect((screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }) as HTMLButtonElement).disabled).toBe(false)
  expect(calls.filter(call => call.method !== 'GET')).toHaveLength(0)
  fireEvent.change(screen.getByLabelText('Fecha 1', { exact: true }), { target: { value: '2026-11-05' } })
  expect((screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.guardar_tarea') }))
  await screen.findByText(t('agents.AgentTasks.tarea_guardada'))
  expect(calls.filter(call => call.method === 'POST')).toHaveLength(0)
  expect(calls.find(call => call.method === 'PUT')?.body).toMatchObject({ expected_revision: 'revision_1', task: { dates: [{ value: '2026-11-05' }] } })
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }))
  await screen.findByText('run_new')
  expect(calls.find(call => call.method === 'POST')?.body).toEqual({ expected_revision: 'revision_2', confirmed: true, source_run_id: null })
})

it('prepares a historical copy, preserves source through date edits and save, and renders history dates readonly', async () => {
  const { calls } = server({ runs: [oldRun] })
  const { container } = render(<AgentTasks />)
  await chooseAgent()
  const history = screen.getByRole('region', { name: t('agents.AgentTasks.historial_de_tareas') })
  expect(history.querySelector('input')).toBeNull()
  expect(container.querySelector('script')).toBeNull()
  expect(screen.getByText('<script>alert(1)</script>')).toBeTruthy()
  fireEvent.click(within(history).getByRole('button', { name: t('agents.AgentTasks.relanzar'), hidden: true }))
  expect((screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }) as HTMLButtonElement).disabled).toBe(true)
  expect(calls.filter(call => call.method !== 'GET')).toHaveLength(0)
  fireEvent.change(screen.getByLabelText('Fecha 1', { exact: true }), { target: { value: '2027-01-01' } })
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.guardar_tarea') }))
  await screen.findByText(t('agents.AgentTasks.tarea_guardada'))
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }))
  await screen.findByText('run_new')
  expect(calls.find(call => call.method === 'POST')?.body.source_run_id).toBe('run_old')
  expect(history.textContent).toContain('2026-10-20')
  expect(oldRun.task_snapshot.dates[0].value).toBe('2026-10-20')
})

it('retains draft prompt and dates after a stale save rejection', async () => {
  server({ failSave: true })
  render(<AgentTasks />)
  await chooseAgent()
  fireEvent.change(screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }), { target: { value: 'Mi borrador pendiente' } })
  fireEvent.change(screen.getByLabelText('Fecha 1', { exact: true }), { target: { value: '2026-12-01' } })
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.guardar_tarea') }))
  await screen.findByRole('alert')
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe('Mi borrador pendiente')
  expect((screen.getByLabelText('Fecha 1', { exact: true }) as HTMLInputElement).value).toBe('2026-12-01')
  expect((screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }) as HTMLButtonElement).disabled).toBe(true)
})

it('starts a legacy agent from description as an unsaved task', async () => {
  server({ legacy: true })
  render(<AgentTasks />)
  await chooseAgent()
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe('Tarea antigua')
  expect(screen.getByText(t('agents.AgentTasks.sin_guardar'))).toBeTruthy()
  expect((screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }) as HTMLButtonElement).disabled).toBe(true)
})

it('reloads the saved date and prompt after leaving and reopening the screen', async () => {
  server()
  const first = render(<AgentTasks />)
  await chooseAgent()
  fireEvent.change(screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }), { target: { value: 'Tarea conservada' } })
  fireEvent.change(screen.getByLabelText('Fecha 1', { exact: true }), { target: { value: '2027-02-01' } })
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.guardar_tarea') }))
  await screen.findByText(t('agents.AgentTasks.tarea_guardada'))
  first.unmount()
  render(<AgentTasks />)
  await chooseAgent()
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe('Tarea conservada')
  expect((screen.getByLabelText('Fecha 1', { exact: true }) as HTMLInputElement).value).toBe('2027-02-01')
  expect(screen.getByText(t('agents.AgentTasks.guardada'))).toBeTruthy()
})

it('distinguishes failed and running history from a received answer', async () => {
  server({ runs: [{ ...oldRun, run_id: 'failed', status: 'failed', answer: null, error: { code: 'provider_unavailable', message: 'Proveedor no disponible.' } }, { ...oldRun, run_id: 'running', status: 'running', completed_at: null, answer: null }] })
  render(<AgentTasks />)
  await chooseAgent()
  expect(screen.getByText(t('agents.aux.state.FAIL'))).toBeTruthy()
  expect(screen.getByText(t('agents.aux.state.running'))).toBeTruthy()
  expect(screen.queryByText(t('agents.AgentTasks.respuesta_recibida'))).toBeNull()
  expect(screen.getByText('provider_unavailable')).toBeTruthy()
})

it('shows load failure and empty agent state explicitly', async () => {
  server({ failTask: true })
  const view = render(<AgentTasks />)
  await screen.findByRole('option', { name: 'Uno' })
  fireEvent.change(screen.getByRole('combobox', { name: t('agents.AgentTasks.agente_para_tareas') }), { target: { value: 'one' } })
  await screen.findByText(/Tareas no disponibles./)
  expect(screen.queryByRole('textbox', { name: t('agents.AgentTaskForm.tarea') })).toBeNull()
  view.unmount()
  vi.stubGlobal('fetch', vi.fn(async () => response({ agents: [] })))
  render(<AgentTasks />)
  await screen.findByText(t('agents.AgentTasks.crea_un_agente_para_guardar_su_tarea'))
})

it('clears old agent fields and ignores an out-of-order response', async () => {
  let resolveOne: (value: unknown) => void = () => {}
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const url = String(input)
    if (url === '/api/agents/list') return response({ agents: [{ id: 'one', config: { name: 'Uno', description: '' } }, { id: 'two', config: { name: 'Dos', description: '' } }] })
    if (url.includes('task-runs')) return response({ runs: [] })
    if (url.includes('/one/')) return new Promise(resolve => { resolveOne = resolve })
    return response({ agent_id: 'two', task: { prompt: 'Solo dos', dates: [] }, revision: 'two' })
  }))
  render(<AgentTasks />)
  await screen.findByRole('option', { name: 'Uno' })
  const selector = screen.getByRole('combobox', { name: t('agents.AgentTasks.agente_para_tareas') })
  fireEvent.change(selector, { target: { value: 'one' } })
  expect(screen.getByText(t('agents.AgentTasks.cargando_tarea'))).toBeTruthy()
  fireEvent.change(selector, { target: { value: 'two' } })
  await screen.findByDisplayValue('Solo dos')
  resolveOne(response({ agent_id: 'one', task, revision: 'one' }))
  await waitFor(() => expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe('Solo dos'))
  expect(screen.queryByLabelText('Fecha 1', { exact: true })).toBeNull()
})

it('Builder keeps imported task fields and initializes an absent task from the description', async () => {
  server()
  const config = { name: 'Importado', description: 'Descripción inicial', type: 'rag' as const, system_prompt: '', tools: [], task }
  const first = render(<AgentBuilder initialAgent={config} agentId="one" />)
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe(task.prompt)
  expect((screen.getByLabelText('Fecha 1', { exact: true }) as HTMLInputElement).value).toBe('2026-10-20')
  first.unmount()
  render(<AgentBuilder initialAgent={{ ...config, task: null }} agentId="one" />)
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe('Descripción inicial')
})

it('validates calendar dates, duplicate keys and maximum rows without throwing', () => {
  expect(taskError(task)).toBe('')
  expect(taskError({ ...task, dates: [{ ...task.dates[0], value: '2026-99-99' }] })).toBe('Revisa las fechas.')
  expect(taskError({ ...task, dates: [{ ...task.dates[0], value: '2026-02-30' }] })).toBe('Revisa las fechas.')
  expect(taskError({ ...task, dates: [task.dates[0], task.dates[0]] })).toContain('clave única')
  expect(taskError({ prompt: ' ', dates: [] })).toContain('Escribe una tarea')
})

it.each([
  { name: 'wrong task owner', target: '/task', body: { agent_id: 'two', task, revision: 'wrong' } },
  { name: 'invalid task dates', target: '/task', body: { agent_id: 'one', task: { prompt: 'Tarea', dates: null }, revision: 'wrong' } },
  { name: 'wrong history owner', target: '/task-runs?limit=50', body: { runs: [{ ...oldRun, agent_id: 'two' }] } },
  { name: 'invalid run status', target: '/task-runs?limit=50', body: { runs: [{ ...oldRun, status: 'completed' }] } },
])('rejects $name without displaying another agent task or malformed history', async ({ target, body }) => {
  const { fetch } = server()
  const fallback = fetch.getMockImplementation()!
  fetch.mockImplementation(async (input, init) => String(input).endsWith(target) ? response(body) : fallback(input, init))
  render(<AgentTasks />)
  await screen.findByRole('option', { name: 'Uno' })
  fireEvent.change(screen.getByRole('combobox', { name: t('agents.AgentTasks.agente_para_tareas') }), { target: { value: 'one' } })
  await screen.findByRole('alert')
  if (target === '/task') expect(screen.queryByRole('textbox', { name: t('agents.AgentTaskForm.tarea') })).toBeNull()
  expect(screen.queryByText('run_old')).toBeNull()
})

it('rejects a mismatched run response without promoting it to successful history', async () => {
  const { fetch } = server()
  const fallback = fetch.getMockImplementation()!
  fetch.mockImplementation(async (input, init) => init?.method === 'POST' ? response({ ...oldRun, agent_id: 'two' }) : fallback(input, init))
  render(<AgentTasks />)
  await chooseAgent()
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }))
  await screen.findByRole('alert')
  expect(screen.queryByText('run_old')).toBeNull()
  expect(screen.queryByText(t('agents.AgentTasks.respuesta_recibida'))).toBeNull()
})

it.each([
  { name: 'stale saved revision', patch: { task_revision: 'stale_revision' } },
  { name: 'missing revision', patch: { task_revision: undefined } },
  { name: 'missing run ID', patch: { run_id: undefined } },
  { name: 'different task prompt', patch: { task_snapshot: { ...task, prompt: 'Otra tarea' } } },
  { name: 'different task date', patch: { task_snapshot: { ...task, dates: [{ ...task.dates[0], value: '2027-01-01' }] } } },
  { name: 'different date label', patch: { task_snapshot: { ...task, dates: [{ ...task.dates[0], label: 'Otra fecha' }] } } },
  { name: 'different source run', patch: { source_run_id: 'another_run' } },
  { name: 'missing source run', patch: { source_run_id: undefined } },
  { name: 'answered without answer', patch: { answer: null } },
  { name: 'answered with empty answer', patch: { answer: ' ' } },
  { name: 'answered without completion', patch: { completed_at: null } },
  { name: 'answered with error', patch: { error: { code: 'error', message: 'Error' } } },
  { name: 'failed without error', patch: { status: 'failed', answer: null, error: null } },
  { name: 'running with completed answer', patch: { status: 'running' } },
  { name: 'completion preceding creation', patch: { completed_at: '2026-10-18T10:00:00Z' } },
])('rejects $name from POST without claiming a received response', async ({ patch }) => {
  const { fetch } = server()
  const fallback = fetch.getMockImplementation()!
  fetch.mockImplementation(async (input, init) => init?.method === 'POST' ? response({ ...oldRun, run_id: 'run_fresh', task_revision: 'revision_1', ...patch }) : fallback(input, init))
  render(<AgentTasks />)
  await chooseAgent()
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }))
  await screen.findByRole('alert')
  expect(screen.queryByText('run_fresh')).toBeNull()
  expect(screen.queryByText(t('agents.AgentTasks.respuesta_recibida'))).toBeNull()
  expect(screen.getByText(t('agents.AgentTasks.sin_ejecuciones'))).toBeTruthy()
  expect((screen.getByRole('textbox', { name: t('agents.AgentTaskForm.tarea') }) as HTMLTextAreaElement).value).toBe(task.prompt)
})

it('rejects reusing a known historical run ID as the new execution result', async () => {
  const { fetch } = server({ runs: [oldRun] })
  const fallback = fetch.getMockImplementation()!
  fetch.mockImplementation(async (input, init) => init?.method === 'POST' ? response({ ...oldRun, task_revision: 'revision_1' }) : fallback(input, init))
  render(<AgentTasks />)
  await chooseAgent()
  await screen.findByText('run_old')
  fireEvent.click(screen.getByRole('button', { name: t('agents.AgentTasks.ejecutar_tarea') }))
  await screen.findByRole('alert')
  expect(screen.getAllByText('run_old')).toHaveLength(1)
  expect(screen.getAllByText(t('agents.AgentTasks.respuesta_recibida'))).toHaveLength(1)
})

it.each([
  { name: 'answered with null answer', patch: { answer: null } },
  { name: 'answered with null completion', patch: { completed_at: null } },
  { name: 'failed without error', patch: { status: 'failed', answer: null } },
  { name: 'running with answer', patch: { status: 'running', completed_at: null } },
])('rejects incoherent historical outcome: $name', async ({ patch }) => {
  server({ runs: [{ ...oldRun, ...patch }] })
  render(<AgentTasks />)
  await chooseAgent()
  await screen.findByRole('alert')
  expect(screen.queryByText('run_old')).toBeNull()
  expect(screen.queryByText(t('agents.AgentTasks.respuesta_recibida'))).toBeNull()
})
