// @vitest-environment jsdom
import React from 'react'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {resetLocaleForTests, setLocale, t} from '../src/i18n'
import {ChatDictationButton, splitSpeechText} from '../src/components/ChatVoiceControls'

let recorder: FakeMediaRecorder | null = null
class FakeMediaRecorder {
  static isTypeSupported() { return true }
  state: RecordingState = 'inactive'
  mimeType = 'audio/webm'
  ondataavailable: ((event: BlobEvent) => void) | null = null
  onerror: (() => void) | null = null
  onstop: (() => void) | null = null
  constructor(_stream: MediaStream) { recorder = this }
  start() { this.state = 'recording' }
  stop() { this.state = 'inactive'; queueMicrotask(() => this.onstop?.()) }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); resetLocaleForTests(); recorder = null })

it('splits long speech without loss and respects the request size limit', () => {
  const source = `${'á'.repeat(2999)}😀${'invoice number 123 — '.repeat(400)}`
  const chunks = splitSpeechText(source)
  expect(chunks.join('')).toBe(source)
  expect(chunks.every(chunk => Array.from(chunk).length <= 3000)).toBe(true)
  expect(chunks.every(chunk => !chunk.includes('\uFFFD'))).toBe(true)
})

it('discards partial audio after a recorder error and stops its microphone stream', async () => {
  setLocale('es')
  const stopTrack = vi.fn()
  const stream = {getTracks: () => [{stop: stopTrack}]} as unknown as MediaStream
  const getUserMedia = vi.fn(async () => stream)
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia}})
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)

  render(<ChatDictationButton onTranscript={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  await waitFor(() => expect(recorder?.state).toBe('recording'))
  recorder?.ondataavailable?.({data: new Blob(['partial'])} as BlobEvent)
  recorder?.onerror?.()
  recorder?.stop()

  await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())
  expect(stopTrack).toHaveBeenCalled()
  expect(fetch).not.toHaveBeenCalled()
})

it('ignores a late microphone grant after cancel and never opens a second acquisition', async () => {
  setLocale('es')
  const stopTrack = vi.fn()
  const stream = {getTracks: () => [{stop: stopTrack}]} as unknown as MediaStream
  let resolveStream: (value: MediaStream) => void = () => {}
  const getUserMedia = vi.fn(() => new Promise<MediaStream>(resolve => { resolveStream = resolve }))
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia}})
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)

  render(<ChatDictationButton onTranscript={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.discard')}))
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  expect(getUserMedia).toHaveBeenCalledTimes(1)
  resolveStream(stream)
  await waitFor(() => expect(stopTrack).toHaveBeenCalledOnce())
  expect(recorder).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})


it.each(['constructor', 'start', 'start_after_recording'] as const)('releases microphone and never uploads if recorder %s fails', async failure => {
  setLocale('es')
  const stopTrack = vi.fn()
  const stream = {getTracks: () => [{stop: stopTrack}]} as unknown as MediaStream
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia: vi.fn(async () => stream)}})
  class FailingRecorder extends FakeMediaRecorder {
    constructor(input: MediaStream) { super(input); if (failure === 'constructor') throw new Error('constructor failed') }
    start() { if (failure === 'start') throw new Error('start failed'); super.start(); if (failure === 'start_after_recording') throw new Error('late start failure') }
  }
  vi.stubGlobal('MediaRecorder', FailingRecorder)
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  const onTranscript = vi.fn()
  render(<ChatDictationButton onTranscript={onTranscript} />)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())
  expect(stopTrack).toHaveBeenCalled()
  expect(fetch).not.toHaveBeenCalled()
  expect(onTranscript).not.toHaveBeenCalled()
})

it.each(['conversation', 'project'] as const)('rejects a late transcript after %s changes', async changed => {
  setLocale('es')
  const stopTrack = vi.fn()
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia: vi.fn(async () => ({getTracks: () => [{stop: stopTrack}]}))}})
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  let finish: (value: unknown) => void = () => {}
  const fetch = vi.fn(() => new Promise(resolve => { finish = resolve })); vi.stubGlobal('fetch', fetch)
  const first = vi.fn(), second = vi.fn()
  const identity = (project: string, conversation: string) => JSON.stringify(['owner', project, conversation])
  const {rerender} = render(<ChatDictationButton key={identity('p1', 'c1')} onTranscript={first} />)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  await waitFor(() => expect(recorder?.state).toBe('recording'))
  recorder?.ondataavailable?.({data: new Blob(['synthetic'])} as BlobEvent)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.stop_dictation')}))
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
  const signal = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1].signal as AbortSignal
  rerender(<ChatDictationButton key={identity(changed === 'project' ? 'p2' : 'p1', changed === 'conversation' ? 'c2' : 'c1')} onTranscript={second} />)
  expect(signal.aborted).toBe(true)
  finish({ok: true, json: async () => ({text: 'resultado tardío'})})
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(stopTrack).toHaveBeenCalled()
  expect(first).not.toHaveBeenCalled()
  expect(second).not.toHaveBeenCalled()
})

it('stops recording without uploading when context changes', async () => {
  setLocale('es')
  const stopTrack = vi.fn()
  Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia: vi.fn(async () => ({getTracks: () => [{stop: stopTrack}]}))}})
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const {rerender} = render(<ChatDictationButton key="conversation-a" onTranscript={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', {name: t('commerce.voice.dictate')}))
  await waitFor(() => expect(recorder?.state).toBe('recording'))
  recorder?.ondataavailable?.({data: new Blob(['synthetic'])} as BlobEvent)
  rerender(<ChatDictationButton key="conversation-b" onTranscript={vi.fn()} />)
  await waitFor(() => expect(stopTrack).toHaveBeenCalled())
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(fetch).not.toHaveBeenCalled()
})
