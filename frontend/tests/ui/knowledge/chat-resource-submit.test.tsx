// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import ChatTools from '../../../src/components/ChatTools'
import {resetLocaleForTests, setLocale} from '../../../src/i18n'

beforeEach(() => {
  localStorage.clear(); resetLocaleForTests(); setLocale('en')
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks()})

function openSourceTool() {
  const composerSubmit = vi.fn((event: React.FormEvent) => event.preventDefault())
  const fetch = vi.fn(async () => ({ok:true, status:200, json:async () => ({
    run_id:'rag-dialog', status:'answered',
    ingestion:{receipt_id:'receipt-dialog',source_path:'docs/guide.md',source_sha256:'a'.repeat(64)},
    retrieval:{hits:[{evidence:{source_uri:'docs/guide.md',revision:'a'.repeat(64)}}]},
    generation:{provider_id:'fixture',model_id:'fixture-model',answer:'Source-backed answer'},
    trace:{trace_id:'trace-dialog',sha256:'b'.repeat(64)},
  })}))
  vi.stubGlobal('fetch', fetch)
  render(<div className="control-chat"><form onSubmit={composerSubmit}>
    <label>Unsent chat draft<textarea defaultValue="Keep this unsent draft" /></label>
    <ChatTools />
  </form></div>)
  fireEvent.click(screen.getByText('Resources', {exact:true}))
  fireEvent.click(screen.getByRole('button', {name:'Consult file'}))
  return {composerSubmit,fetch}
}

it('keeps the source dialog and its form outside the chat message form', () => {
  openSourceTool()
  const dialog = screen.getByRole('dialog', {name:'Consult file'})
  expect(dialog.closest('form')).toBeNull()
  expect(dialog.closest('.control-chat')).not.toBeNull()
  expect(screen.getByRole('form', {name:'Index local source and ask'}).parentElement?.closest('form')).toBeNull()
})

it('submits the source once without submitting or discarding a pending chat draft', async () => {
  const {composerSubmit,fetch}=openSourceTool()
  fireEvent.change(screen.getByLabelText('Project-relative file path'),{target:{value:'docs/guide.md'}})
  fireEvent.change(screen.getByLabelText('Question'),{target:{value:'What does this source say?'}})
  fireEvent.click(screen.getByRole('button',{name:'Index source and answer'}))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  expect(fetch.mock.calls[0]).toEqual(['/api/knowledge/ingest-and-answer',expect.objectContaining({method:'POST'})])
  await screen.findByRole('region',{name:'Grounded retrieval result'})
  expect(composerSubmit).not.toHaveBeenCalled()
  expect((screen.getByLabelText('Unsent chat draft') as HTMLTextAreaElement).value).toBe('Keep this unsent draft')
})
