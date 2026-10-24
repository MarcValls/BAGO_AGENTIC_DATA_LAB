import {presentAgentError} from '../../components/AgentTaskForm'
import {AgentPresentationError} from '../../components/AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../../i18n'
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
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.this_file_is_not_a_complete_successful_ber_effect_record'))
  }
  if (ber.version !== BER_RECORD_IDENTITY.version || ber.protocol_version !== BER_RECORD_IDENTITY.protocol || ber.source_commit !== BER_RECORD_IDENTITY.sourceCommit || ber.artifact_sha256 !== BER_RECORD_IDENTITY.artifactSha256) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.ber_version_protocol_source_commit_or_artifact_digest_does_not_match_t'))
  }

  const effectId = string(prepared.effect_id)
  const requestId = string(prepared.request_id)
  const executionId = string(execution.ber_execution_id)
  const receiptId = string(execution.receipt_id)
  const traceId = string(trace.trace_id)
  if (!effectId || !supportedEffects.has(effectId) || !requestId || !executionId || !receiptId || !traceId) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.the_record_is_missing_a_supported_effect_or_required_ber_identity'))
  }
  if (execution.request_id !== requestId || execution.effect_id !== effectId || result.receipt_id !== receiptId || result.ok !== true || result.executed !== true) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.execution_request_or_receipt_identity_does_not_match_the_prepared_effe'))
  }
  if (prepared.approval_required === true) {
    if (approval?.state !== 'approved' || approval.request_id !== requestId || approval.effect_id !== effectId || !string(approval.decision_id) || authorization.decision_id !== approval.decision_id || !string(approval.proof_id) || authorization.proof_id !== approval.proof_id || !string(authorization.permit_id)) {
      throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.the_mutating_effect_lacks_a_matching_bago_approval_and_permit_identity'))
    }
  }
  if (evaluation.status !== 'PASS' || !Array.isArray(evaluation.evidence_refs) || !evaluation.evidence_refs.includes(`ber://receipt/${receiptId}`)) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.evaluation_is_not_linked_to_the_bago_receipt'))
  }
  if (trace.run_id !== executionId || !Array.isArray(trace.events) || trace.events.length === 0) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.localtrace_is_missing_or_does_not_match_the_ber_execution_identity'))
  }
  const events = trace.events.map(object)
  if (events.some(event => !event || event.trace_id !== traceId || !string(event.event_id))) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.localtrace_event_identity_does_not_match_its_trace_envelope'))
  }
  const ids = events.map(event => event?.event_id)
  if (new Set(ids).size !== ids.length) throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.localtrace_contains_duplicate_event_ids'))
  const receiptEvent = events.find(event => event?.name === 'ber.receipt')
  const receiptAttributes = object(receiptEvent?.attributes)
  const effectEvent = events.find(event => event?.name === 'ber.effect')
  const effectAttributes = object(effectEvent?.attributes)
  if (receiptAttributes?.receipt_id !== receiptId || receiptAttributes.request_id !== requestId || effectAttributes?.effect_id !== effectId || effectAttributes.request_id !== requestId) {
    throw new AgentPresentationError(() => t('agents.BerEffectRecordInspector.localtrace_effect_or_receipt_event_does_not_match_the_ber_execution'))
  }

  return { source, ber, prepared, execution, result, authorization, trace, events: events as JsonRecord[], evaluation }
}

const MAX_RECORD_BYTES = 1_048_576

export function BerEffectRecordInspector() {
  useI18n()
  const [record, setRecord] = useState<ValidatedBerEffectRecord>()
  const [error, setError] = useState<string | Error>()
  const [filename, setFilename] = useState<string>()

  async function loadFile(file?: File) {
    setRecord(undefined)
    setFilename(undefined)
    setError(undefined)
    if (!file) return
    if (file.size > MAX_RECORD_BYTES) {
      setError(new AgentPresentationError(() => t('agents.BerEffectRecordInspector.the_record_exceeds_the_1_mib_import_limit')))
      return
    }
    try {
      const parsed: unknown = JSON.parse((await file.text()).replace(/^\uFEFF/, ''))
      setRecord(validateBerEffectRecord(parsed))
      setFilename(file.name)
    } catch (cause) {
      setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.BerEffectRecordInspector.the_selected_file_could_not_be_read_as_a_ber_record')))
    }
  }

  return <main className="ber-effect-record" aria-labelledby="ber-effect-record-title">
    <header className="ber-effect-record__header">
      <p className="app-kicker">{t('agents.BerEffectRecordInspector.read_only_evidence')}</p>
      <h1 id="ber-effect-record-title">{t('agents.BerEffectRecordInspector.ber_effect_record')}</h1>
      <p>{t('agents.BerEffectRecordInspector.inspect_a_json_record_emitted_by_adl_s_explicit_ber_effect_demo_this_v')}</p>
    </header>
    <label className="ber-effect-record__file">{t('agents.BerEffectRecordInspector.choose_ber_effect_json')} <input type="file" accept="application/json,.json" onChange={event => void loadFile(event.currentTarget.files?.[0])} />
    </label>
    {error && <p className="ber-effect-record__message ber-effect-record__message--error" role="alert">{typeof error === 'string' ? error : presentAgentError(error)}</p>}
    {!record && !error && <p className="ber-effect-record__message" role="status">{t('agents.BerEffectRecordInspector.no_record_loaded_select_a_json_file_produced_by')} <code>scripts/ber_effect_demo.py</code>.</p>}
    {record && <>
      <p className="ber-effect-record__message" role="status">{t('agents.BerEffectRecordInspector.validated_source_supplied_record')} <strong>{filename}</strong>{t('agents.BerEffectRecordInspector.validation_checks_format_and_matching_ids_it_does_not_verify_a_signatu')}</p>
      <section aria-labelledby="ber-record-identity-title">
        <h2 id="ber-record-identity-title">{t('agents.BerEffectRecordInspector.bago_runtime_identity')}</h2>
        <dl className="ber-effect-record__grid">
          <div><dt>{t('agents.BerEffectRecordInspector.ber_version')}</dt><dd>{String(record.ber.version)}</dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.protocol')}</dt><dd><code>{String(record.ber.protocol_version)}</code></dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.source_commit')}</dt><dd><code>{String(record.ber.source_commit)}</code></dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.artifact_sha_256')}</dt><dd><code>{String(record.ber.artifact_sha256)}</code></dd></div>
          <div><dt>{t('agents.AgentRunner.effect')}</dt><dd>{String(record.prepared.effect_id)}</dd></div>
          <div><dt>{t('agents.AgentRunner.request_id')}</dt><dd><code>{String(record.prepared.request_id)}</code></dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.execution_id')}</dt><dd><code>{String(record.execution.ber_execution_id)}</code></dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.bago_receipt_id')}</dt><dd><code>{String(record.execution.receipt_id)}</code></dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.authorization')}</dt><dd>{string(record.authorization.state) ?? t('agents.AgentRunner.not_provided')}</dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.evaluation')}</dt><dd>{String(record.evaluation.status)}</dd></div>
          <div><dt>{t('agents.BerEffectRecordInspector.adl_localtrace_id')}</dt><dd><code>{String(record.trace.trace_id)}</code></dd></div>
        </dl>
      </section>
      <section aria-labelledby="ber-record-trace-title">
        <h2 id="ber-record-trace-title">{t('agents.BerEffectRecordInspector.adl_localtrace_projection')}</h2>
        <p>{t('agents.BerEffectRecordInspector.adl_trace_evidence_is_a_projection_of_bago_s_outcome_it_is_not_the_exe')}</p>
        <ol className="ber-effect-record__events">{record.events.map(event => <li key={String(event.event_id)}>
          <strong>{string(event.name) ?? t('agents.BerEffectRecordInspector.event_name_not_provided')}</strong>
          <span>{string(event.status) ?? t('agents.BerEffectRecordInspector.status_not_provided')}</span>
          <code>{String(event.event_id)}</code>
        </li>)}</ol>
      </section>
    </>}
  </main>
}
