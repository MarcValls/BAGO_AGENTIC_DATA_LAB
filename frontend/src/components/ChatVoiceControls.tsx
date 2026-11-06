import {useEffect, useRef, useState} from 'react'
import {t, useI18n, type TranslationKey} from '../i18n'

type VoiceState = 'idle' | 'starting' | 'recording' | 'transcribing' | 'speaking' | 'done' | 'error'

function voiceErrorLabel(code: string): string {
  const known: Record<string, string> = {
    voice_microphone_unavailable: 'commerce.voice.errors.microphone_unavailable',
    voice_microphone_denied: 'commerce.voice.errors.microphone_denied',
    voice_microphone_failed: 'commerce.voice.errors.microphone_failed',
    voice_recording_failed: 'commerce.voice.errors.recording_failed',
    voice_audio_empty: 'commerce.voice.errors.audio_empty',
    voice_transcript_empty: 'commerce.voice.errors.transcript_empty',
    voice_runtime_unavailable: 'commerce.voice.errors.runtime_unavailable',
    voice_port_in_use: 'commerce.voice.errors.port_in_use',
    voice_start_timeout: 'commerce.voice.errors.start_timeout',
    voice_audio_too_large: 'commerce.voice.errors.audio_too_large',
    voice_audio_format_unsupported: 'commerce.voice.errors.audio_format_unsupported',
    voice_playback_failed: 'commerce.voice.errors.playback_failed',
    voice_playback_timeout: 'commerce.voice.errors.playback_timeout',
    voice_request_failed: 'commerce.voice.errors.request_failed',
    voice_response_invalid: 'commerce.voice.errors.request_failed',
    voice_config_invalid: 'commerce.voice.errors.runtime_unavailable',
  }
  return t((known[code] ?? known.voice_request_failed) as TranslationKey)
}

async function readApiError(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    const detail = payload?.detail
    const code = typeof detail === 'string' ? detail : detail?.code
    return typeof code === 'string' ? code : 'voice_request_failed'
  } catch { return 'voice_request_failed' }
}

export function ChatDictationButton({disabled, onTranscript}: {disabled?: boolean; onTranscript: (text: string) => void}) {
  useI18n()
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState('')
  const recorderRef = useRef<MediaRecorder|null>(null)
  const streamRef = useRef<MediaStream|null>(null)
  const chunksRef = useRef<Blob[]>([])
  const discardRef = useRef(false)
  const mountedRef = useRef(true)
  const limitTimerRef = useRef<number|null>(null)
  const acquiringRef = useRef(false)
  const acquisitionCancelledRef = useRef(false)
  const recorderFailedRef = useRef(false)
  const transcriptionRef = useRef<AbortController|null>(null)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      discardRef.current = true
      acquisitionCancelledRef.current = true
      transcriptionRef.current?.abort()
      if (limitTimerRef.current !== null) window.clearTimeout(limitTimerRef.current)
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      streamRef.current?.getTracks().forEach(track => track.stop())
    }
  }, [])

  const start = async () => {
    if (acquiringRef.current || recorderRef.current?.state === 'recording' || state === 'transcribing') return
    acquiringRef.current = true
    acquisitionCancelledRef.current = false
    setError('')
    setState('starting')
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('voice_microphone_unavailable')
      const stream = await navigator.mediaDevices.getUserMedia({audio: true})
      if (!mountedRef.current || acquisitionCancelledRef.current) { stream.getTracks().forEach(track => track.stop()); return }
      streamRef.current = stream
      const mimeType = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type))
      const recorder = mimeType ? new MediaRecorder(stream, {mimeType}) : new MediaRecorder(stream)
      recorderRef.current = recorder
      chunksRef.current = []
      discardRef.current = false
      recorderFailedRef.current = false
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onerror = () => {
        discardRef.current = true
        recorderFailedRef.current = true
        chunksRef.current = []
        if (limitTimerRef.current !== null) { window.clearTimeout(limitTimerRef.current); limitTimerRef.current = null }
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        recorderRef.current = null
        if (recorder.state === 'recording') { try { recorder.stop() } catch { /* Failed recorders cannot be restarted. */ } }
        if (mountedRef.current) { setState('error'); setError('voice_recording_failed') }
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        recorderRef.current = null
        if (discardRef.current) { chunksRef.current = []; if (mountedRef.current) setState(recorderFailedRef.current ? 'error' : 'idle'); return }
        const blob = new Blob(chunksRef.current, {type: recorder.mimeType || 'audio/webm'})
        chunksRef.current = []
        if (!blob.size) { if (mountedRef.current) { setState('error'); setError('voice_audio_empty') }; return }
        if (mountedRef.current) setState('transcribing')
        try {
          const controller = new AbortController()
          transcriptionRef.current = controller
          const response = await fetch('/api/voice/transcribe', {method: 'POST', headers: {'Content-Type': blob.type.split(';')[0]}, body: blob, signal: controller.signal})
          if (!response.ok) throw new Error(await readApiError(response))
          const result = await response.json() as {text?: unknown}
          if (typeof result.text !== 'string' || !result.text.trim()) throw new Error('voice_transcript_empty')
          if (mountedRef.current) { onTranscript(result.text.trim()); setState('done') }
        } catch (cause) { if (mountedRef.current) { setState('error'); setError(cause instanceof Error ? cause.message : 'voice_request_failed') } }
        finally { transcriptionRef.current = null }
      }
      recorder.start(250)
      limitTimerRef.current = window.setTimeout(() => stop(false), 60_000)
      setState('recording')
    } catch (cause) {
      discardRef.current = true
      recorderFailedRef.current = true
      chunksRef.current = []
      if (limitTimerRef.current !== null) { window.clearTimeout(limitTimerRef.current); limitTimerRef.current = null }
      const recorder = recorderRef.current
      recorderRef.current = null
      if (recorder?.state === 'recording') { try { recorder.stop() } catch { /* Still release the microphone. */ } }
      streamRef.current?.getTracks().forEach(track => track.stop())
      streamRef.current = null
      if (mountedRef.current && !acquisitionCancelledRef.current) {
        setState('error')
        setError(cause instanceof Error && cause.message === 'voice_microphone_unavailable' ? cause.message : cause instanceof DOMException && cause.name === 'NotAllowedError' ? 'voice_microphone_denied' : 'voice_microphone_failed')
      }
    } finally {
      acquiringRef.current = false
      if (mountedRef.current && acquisitionCancelledRef.current) setState('idle')
    }
  }

  const stop = (discard: boolean) => {
    if (limitTimerRef.current !== null) { window.clearTimeout(limitTimerRef.current); limitTimerRef.current = null }
    discardRef.current = discard
    if (state === 'starting') { acquisitionCancelledRef.current = true; return }
    const recorder = recorderRef.current
    if (recorder?.state === 'recording') recorder.stop()
    else if (discard) { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; setState('idle') }
  }

  const label = state === 'recording' ? t('commerce.voice.stop_dictation') : state === 'transcribing' ? t('commerce.voice.transcribing') : t('commerce.voice.dictate')
  return <div className="chat-voice-control">
    <button type="button" className={`chat-voice-button ${state === 'recording' ? 'is-recording' : ''}`} disabled={disabled || state === 'starting' || state === 'transcribing'} aria-label={label} title={label} onClick={() => state === 'recording' ? stop(false) : void start()}>
      {state === 'recording' ? <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" /></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3m-4 0h8" /></svg>}
    </button>
    {(state === 'starting' || state === 'recording') && <button type="button" className="chat-voice-cancel" onClick={() => stop(true)}>{t('commerce.voice.discard')}</button>}
    {(state === 'starting' || state === 'transcribing' || state === 'recording') && <span className="chat-voice-status" role="status">{state === 'starting' ? t('commerce.voice.requesting_microphone') : state === 'recording' ? t('commerce.voice.recording') : t('commerce.voice.transcribing')}</span>}
    {state === 'done' && <span className="visually-hidden" role="status">{t('commerce.voice.transcript_ready')}</span>}
    {error && <span className="chat-voice-error" role="alert">{voiceErrorLabel(error)}</span>}
  </div>
}


export function splitSpeechText(text: string, maxLength = 3000): string[] {
  if (!Number.isInteger(maxLength) || maxLength < 1) throw new RangeError('maxLength must be a positive integer')
  const chunks: string[] = []
  const characters = Array.from(text)
  let start = 0
  while (characters.length - start > maxLength) {
    let end = start + maxLength
    const earliest = start + Math.floor(maxLength * 0.6)
    for (let index = end - 1; index >= earliest; index--) {
      if (characters[index] === ' ') { end = index + 1; break }
    }
    chunks.push(characters.slice(start, end).join(''))
    start = end
  }
  if (start < characters.length) chunks.push(characters.slice(start).join(''))
  return chunks
}

export function MessageSpeechButton({text}: {text: string}) {
  useI18n()
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState('')
  const generationRef = useRef(0)

  useEffect(() => () => { generationRef.current++ }, [])

  const speak = async () => {
    const generation = ++generationRef.current
    setState('speaking'); setError('')
    try {
      for (const chunk of splitSpeechText(text)) {
        if (generationRef.current !== generation) return
        const response = await fetch('/api/voice/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: chunk, voice: 'alex', speed: 0.95})})
        if (!response.ok) throw new Error(await readApiError(response))
        const {id} = await response.json() as {id?: string}
        if (!id || !/^[0-9a-f]{32}$/.test(id)) throw new Error('voice_response_invalid')
        let completed = false
        for (let attempt = 0; attempt < 180 && generationRef.current === generation; attempt++) {
          const statusResponse = await fetch(`/api/voice/requests/${id}`, {cache: 'no-store'})
          if (!statusResponse.ok) throw new Error(await readApiError(statusResponse))
          const result = await statusResponse.json() as {status?: string}
          if (result.status === 'PLAYBACK_RETURNED') { completed = true; break }
          if (result.status === 'FAILED') throw new Error('voice_playback_failed')
          await new Promise(resolve => window.setTimeout(resolve, 1000))
        }
        if (!completed) { if (generationRef.current === generation) throw new Error('voice_playback_timeout'); return }
      }
      if (generationRef.current === generation) setState('done')
    } catch (cause) { if (generationRef.current === generation) { setState('error'); setError(cause instanceof Error ? cause.message : 'voice_request_failed') } }
  }

  const label = state === 'speaking' ? t('commerce.voice.speaking') : t('commerce.voice.read_aloud')
  return <span className="chat-message-voice">
    <button type="button" className="message-action" aria-label={label} title={label} disabled={!text.trim() || state === 'speaking'} onClick={() => void speak()}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4h4l5 4V6l-5 4H4Z" /><path d="M16 9a5 5 0 0 1 0 6m2-9a9 9 0 0 1 0 12" /></svg>
      {label}
    </button>
    {state === 'done' && <span className="visually-hidden" role="status">{t('commerce.voice.playback_returned')}</span>}
    {error && <span className="chat-voice-error" role="alert">{voiceErrorLabel(error)}</span>}
  </span>
}
