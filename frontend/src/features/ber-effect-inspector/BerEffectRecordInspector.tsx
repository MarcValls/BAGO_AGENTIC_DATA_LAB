import { useState } from 'react'
import './BerEffectRecordInspector.css'

export const BER_RECORD_SCHEMA = 'bago.ber.effect-demo.v1'
export const BER_RECORD_IDENTITY = {
  version: '0.1.0',
  protocol: 'bago.ber.ipc/v1',
  sourceCommit: '5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d',
  artifactSha256: 'c81ef7f05a3051df8ecbc1a150500ea16ea872fc459fa45881488c91e83843d3',
} as const

type JsonRecord = Record<string, unknown>

function object(value: unknown): JsonRecord | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : undefined
}

function string(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined
}

export interface ValidatedBerEffectRecord {
  source: JsonRecord
  ber: JsonRecord
  prepared: JsonRecord
  execution: JsonRecord
  result: JsonRecord
  authorization: JsonRecord
  trace: JsonRecord
  events: JsonRecord[]
  evaluation: JsonRecord
}

export function validateBerEffectRecord(value: unknown): ValidatedBerEffectRecord {
  const source = object(value)
  const ber = object(source?.ber)
  const prepared = object(source?.prepared)
  const execution = object(source?.execution)
  const result = object(execution?.result)
  const authorization = object(execution?.authorization)
  const trace = object(source?.trace)
  const evaluation = object(source?.evaluation)
  const approval = object(source?.approval)
  const supportedEffects = new Set(['filesystem.read', 'filesystem.write', 'process.inspect', 'process.execute'])

  if (source?.schema !== BER_RECORD_SCHEMA || source.status !== 'PASS' || !ber || !prepared || !execution || !result || !authorization || !trace || !evaluation) {
    throw new Error('This file is not a complete successful BER effect record.')
  }
  if (ber.version !== BER_RECORD_IDENTITY.version || ber.protocol_version !== BER_RECORD_IDENTITY.protocol || ber.source_commit !== BER_RECORD_IDENTITY.sourceCommit || ber.artifact_sha256 !== BER_RECORD_IDENTITY.artifactSha256) {
    throw new Error('BER version, protocol, source commit or artifact digest does not match the ADL pin.')
  }

  const effectId = string(prepared.effect_id)
  const requestId = string(prepared.request_id)
  const executionId = string(execution.ber_execution_id)
  const receiptId = string(execution.receipt_id)
  const traceId = string(trace.trace_id)
  if (!effectId || !supportedEffects.has(effectId) || !requestId || !executionId || !receiptId || !traceId) {
    throw new Error('The record is missing a supported effect or required BER identity.')
  }
  if (execution.request_id !== requestId || execution.effect_id !== effectId || result.receipt_id !== receiptId || result.ok !== true || result.executed !== true) {
    throw new Error('Execution request or receipt identity does not match the prepared effect.')
  }
  if (prepared.approval_required === true) {
    if (approval?.state !== 'approved' || approval.request_id !== requestId || approval.effect_id !== effectId || !string(approval.decision_id) || authorization.decision_id !== approval.decision_id || !string(approval.proof_id) || authorization.proof_id !== approval.proof_id || !string(authorization.permit_id)) {
      throw new Error('The mutating effect lacks a matching BAGO approval and permit identity.')
    }
  }
  if (evaluation.status !== 'PASS' || !Array.isArray(evaluation.evidence_refs) || !evaluation.evidence_refs.includes(`ber://receipt/${receiptId}`)) {
    throw new Error('Evaluation is not linked to the BAGO receipt.')
  }
  if (trace.run_id !== executionId || !Array.isArray(trace.events) || trace.events.length === 0) {
    throw new Error('LocalTrace is missing or does not match the BER execution identity.')
  }
  const events = trace.events.map(object)
  if (events.some(event => !event || event.trace_id !== traceId || !string(event.event_id))) {
    throw new Error('LocalTrace event identity does not match its trace envelope.')
  }
  const ids = events.map(event => event?.event_id)
  if (new Set(ids).size !== ids.length) throw new Error('LocalTrace contains duplicate event IDs.')
  const receiptEvent = events.find(event => event?.name === 'ber.receipt')
  const receiptAttributes = object(receiptEvent?.attributes)
  const effectEvent = events.find(event => event?.name === 'ber.effect')
  const effectAttributes = object(effectEvent?.attributes)
  if (receiptAttributes?.receipt_id !== receiptId || receiptAttributes.request_id !== requestId || effectAttributes?.effect_id !== effectId || effectAttributes.request_id !== requestId) {
    throw new Error('LocalTrace effect or receipt event does not match the BER execution.')
  }

  return { source, ber, prepared, execution, result, authorization, trace, events: events as JsonRecord[], evaluation }
}

const MAX_RECORD_BYTES = 1_048_576

export function BerEffectRecordInspector() {
  const [record, setRecord] = useState<ValidatedBerEffectRecord>()
  const [error, setError] = useState<string>()
  const [filename, setFilename] = useState<string>()

  async function loadFile(file?: File) {
    setRecord(undefined)
    setFilename(undefined)
    setError(undefined)
    if (!file) return
    if (file.size > MAX_RECORD_BYTES) {
      setError('The record exceeds the 1 MiB import limit.')
      return
    }
    try {
      const parsed: unknown = JSON.parse((await file.text()).replace(/^\uFEFF/, ''))
      setRecord(validateBerEffectRecord(parsed))
      setFilename(file.name)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The selected file could not be read as a BER record.')
    }
  }

  return <main className="ber-effect-record" aria-labelledby="ber-effect-record-title">
    <header className="ber-effect-record__header">
      <p className="app-kicker">Read-only evidence</p>
      <h1 id="ber-effect-record-title">BER Effect Record</h1>
      <p>Inspect a JSON record emitted by ADL's explicit BER effect demo. This view does not represent an AgentRun or establish cryptographic receipt origin.</p>
    </header>
    <label className="ber-effect-record__file">Choose BER effect JSON
      <input type="file" accept="application/json,.json" onChange={event => void loadFile(event.currentTarget.files?.[0])} />
    </label>
    {error && <p className="ber-effect-record__message ber-effect-record__message--error" role="alert">{error}</p>}
    {!record && !error && <p className="ber-effect-record__message" role="status">No record loaded. Select a JSON file produced by <code>scripts/ber_effect_demo.py</code>.</p>}
    {record && <>
      <p className="ber-effect-record__message" role="status">Validated source-supplied record: <strong>{filename}</strong>. Validation checks format and matching IDs; it does not verify a signature.</p>
      <section aria-labelledby="ber-record-identity-title">
        <h2 id="ber-record-identity-title">BAGO runtime identity</h2>
        <dl className="ber-effect-record__grid">
          <div><dt>BER version</dt><dd>{String(record.ber.version)}</dd></div>
          <div><dt>Protocol</dt><dd><code>{String(record.ber.protocol_version)}</code></dd></div>
          <div><dt>Source commit</dt><dd><code>{String(record.ber.source_commit)}</code></dd></div>
          <div><dt>Artifact SHA-256</dt><dd><code>{String(record.ber.artifact_sha256)}</code></dd></div>
          <div><dt>Effect</dt><dd>{String(record.prepared.effect_id)}</dd></div>
          <div><dt>Request ID</dt><dd><code>{String(record.prepared.request_id)}</code></dd></div>
          <div><dt>Execution ID</dt><dd><code>{String(record.execution.ber_execution_id)}</code></dd></div>
          <div><dt>BAGO receipt ID</dt><dd><code>{String(record.execution.receipt_id)}</code></dd></div>
          <div><dt>Authorization</dt><dd>{string(record.authorization.state) ?? 'Not provided'}</dd></div>
          <div><dt>Evaluation</dt><dd>{String(record.evaluation.status)}</dd></div>
          <div><dt>ADL LocalTrace ID</dt><dd><code>{String(record.trace.trace_id)}</code></dd></div>
        </dl>
      </section>
      <section aria-labelledby="ber-record-trace-title">
        <h2 id="ber-record-trace-title">ADL LocalTrace projection</h2>
        <p>ADL trace evidence is a projection of BAGO's outcome; it is not the execution authority.</p>
        <ol className="ber-effect-record__events">{record.events.map(event => <li key={String(event.event_id)}>
          <strong>{string(event.name) ?? 'Event name not provided'}</strong>
          <span>{string(event.status) ?? 'Status not provided'}</span>
          <code>{String(event.event_id)}</code>
        </li>)}</ol>
      </section>
    </>}
  </main>
}
