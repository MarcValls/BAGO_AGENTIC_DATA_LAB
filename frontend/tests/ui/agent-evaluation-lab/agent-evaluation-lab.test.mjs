import { strict as assert } from 'node:assert'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const source = await readFile(new URL('../../../src/components/AgentEvaluationLab.tsx', import.meta.url), 'utf8')
const start = source.indexOf('async function jsonRequest')
const end = source.indexOf('\nconst newCase', start)
assert.ok(start >= 0 && end > start, 'Evaluation API client block must exist in the component')
const clientSource = source.slice(start, end)
const compiled = ts.transpileModule(clientSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
const exports = {}
vm.runInNewContext(compiled, { exports, fetch: globalThis.fetch })
const { evaluationApi } = exports

const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
const suite = { id: 'evalsuite_abc', name: 'Smoke', agent_id: 'agent_1234abcd', version: 1, revision: 1, cases: [{ id: 'case_1', name: 'Greeting', prompt: 'Say hi', must_include: ['hello'], must_not_include: [] }] }
const run = { id: 'evalrun_1', suite_id: suite.id, suite_version: 1, suite_name: suite.name, agent_id: suite.agent_id, agent_name: 'Assistant', agent_config_fingerprint: 'sha256:abc', provider_id: 'ollama-cloud', model_id: 'gemma4:31b-cloud', status: 'PASS', total_cases: 1, passed_cases: 1, failed_cases: 0, error_cases: 0, duration_ms: 12, started_at: '2026-01-01T00:00:00Z', completed_at: '2026-01-01T00:00:01Z', cases: [] }

test('normal inventory and model discovery use configured APIs and preserve returned identities', async () => {
  const calls = []
  const stub = async (url, init) => { calls.push([url, init]); if (url.endsWith('/agents/list')) return response({ agents: [{ id: suite.agent_id, config: { name: 'Assistant' } }] }); if (url.endsWith('/models')) return response({ models: [{ model_id: run.model_id }] }); if (url.endsWith('/suites')) return response({ suites: [suite] }); return response({ runs: [run] }) }
  assert.equal((await evaluationApi.agents(stub)).agents[0].id, suite.agent_id)
  assert.equal((await evaluationApi.models(stub)).models[0].model_id, run.model_id)
  assert.equal((await evaluationApi.suites(stub)).suites[0].version, 1)
  assert.equal((await evaluationApi.runs(stub)).runs[0].id, run.id)
  assert.equal(calls.length, 4)
})

test('empty suites and history stay empty without fabricating examples', async () => {
  const stub = async () => response({ suites: [], runs: [] })
  assert.deepEqual((await evaluationApi.suites(stub)).suites, [])
  assert.deepEqual((await evaluationApi.runs(stub)).runs, [])
})

test('API errors surface safe backend messages and never become successful runs', async () => {
  const stub = async () => response({ detail: { code: 'provider_unavailable', message: 'Provider is unavailable.' } }, 503)
  await assert.rejects(evaluationApi.agents(stub), /Provider is unavailable/)
  await assert.rejects(evaluationApi.run(suite, run.model_id, stub), /Provider is unavailable/)
})

test('a provider request is made only through explicit run and is bound to saved revision/model', async () => {
  const calls = []
  const stub = async (url, init) => { calls.push([url, init]); return response({ run }) }
  assert.equal(calls.length, 0)
  const result = await evaluationApi.run(suite, run.model_id, stub)
  assert.equal(result.run.id, run.id)
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], `/api/evaluations/suites/${suite.id}/run`)
  assert.equal(calls[0][1].method, 'POST')
  assert.deepEqual(JSON.parse(calls[0][1].body), { revision: suite.revision, model_id: run.model_id })
})

test('suite edits carry expected revision and case assertions', async () => {
  const next = { ...suite, version: 2, revision: 2 }
  let captured
  const stub = async (_url, init) => { captured = JSON.parse(init.body); return response({ suite: next }) }
  const updated = await evaluationApi.updateSuite(suite, { name: suite.name, agent_id: suite.agent_id, cases: suite.cases }, stub)
  assert.equal(updated.suite.version, 2)
  assert.equal(captured.expected_revision, 1)
  assert.deepEqual(captured.cases[0].must_include, ['hello'])
})
