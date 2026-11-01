// @vitest-environment jsdom
import {beforeEach, expect, it, vi} from 'vitest'
import {publicWebPreferenceKey, readPublicWebPreference, writePublicWebPreference, emptyPublicWebNotice, readPublicWebNotice, writePublicWebNotice, type PublicWebIdentity} from '../../src/utils/publicWebPreference'
import {extractPublicHttpsUrls, parsePublicWebScope} from '../../src/utils/publicWebUrls'

const identity: PublicWebIdentity = {projectId: 'p', root: 'D:/project', ownerKind: 'assistant', ownerId: 'app-assistant', conversationId: 'c'}
beforeEach(() => localStorage.clear())

it('round-trips explicit consent only for the exact project/root/owner/conversation and stores no permits', () => {
  expect(writePublicWebPreference(identity, {enabled: true, urls: 'https://example.org/page'})).toBe(true)
  expect(readPublicWebPreference(identity).preference.enabled).toBe(true)
  for (const other of [{projectId: 'other'}, {root: 'D:/other'}, {ownerKind: 'agent' as const}, {ownerId: 'other'}, {conversationId: 'other'}]) {
    expect(readPublicWebPreference({...identity, ...other}).preference.enabled).toBe(false)
  }
  expect(Object.keys(JSON.parse(localStorage.getItem(publicWebPreferenceKey(identity))!)).sort()).toEqual(['enabled', 'urls', 'version'])
  writePublicWebPreference(identity, {enabled: false, urls: 'https://example.org/page'})
  expect(readPublicWebPreference(identity).preference).toEqual({enabled: false, urls: 'https://example.org/page'})
})

it.each(['not-json', '{}', '{"version":0,"enabled":true,"urls":"https://example.org"}', '{"version":1,"enabled":true,"urls":"http://example.org"}', '{"version":1,"enabled":true,"urls":"https://example.org","authorization_id":"legacy"}'])('fails closed on malformed/legacy stored data: %s', raw => {
  localStorage.setItem(publicWebPreferenceKey(identity), raw)
  expect(readPublicWebPreference(identity)).toEqual({preference: {enabled: false, urls: ''}, failed: true})
})

it('fails closed when reading/writing storage is unavailable, including its getter', () => {
  const storage = {getItem() {throw new Error('denied')}, setItem() {throw new Error('full')}}
  expect(readPublicWebPreference(identity, storage).failed).toBe(true)
  expect(writePublicWebPreference(identity, {enabled: true, urls: 'https://example.org'}, storage)).toBe(false)
  const getter = vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {throw new Error('disabled')})
  try {
    expect(readPublicWebPreference(identity).failed).toBe(true)
    expect(writePublicWebPreference(identity, {enabled: true, urls: 'https://example.org'})).toBe(false)
  } finally {getter.mockRestore()}
})

it('an incomplete human scope edit persists OFF instead of restoring an earlier active scope', () => {
  writePublicWebPreference(identity, {enabled: true, urls: 'https://example.org'})
  writePublicWebPreference(identity, {enabled: true, urls: 'https://'})
  expect(readPublicWebPreference(identity).preference).toEqual({enabled: false, urls: ''})
})

it('extracts direct user HTTPS URLs with balanced punctuation and deduplication; parsing does not enable consent', () => {
  expect(extractPublicHttpsUrls('Lee (https://example.org/page), https://example.org/page. Y https://example.org/a_(b).')).toEqual({urls: ['https://example.org/page', 'https://example.org/a_(b)'], invalid: false})
  expect(extractPublicHttpsUrls('http://example.org https://u:p@example.org/ https://example.org:8443/').invalid).toBe(true)
  expect(parsePublicWebScope('https://example.org/a\r\nhttps://example.org/a\nhttps://example.org/b').origins).toEqual(['https://example.org'])
  expect(localStorage.length).toBe(0)
})

it('persists explicit v2 empty ON without legitimizing an invalid v1 empty grant preference', () => {
  localStorage.setItem(publicWebPreferenceKey(identity), JSON.stringify({version: 1, enabled: true, urls: ''}))
  expect(readPublicWebPreference(identity).failed).toBe(true)
  expect(writePublicWebPreference(identity, {enabled: true, urls: ''})).toBe(true)
  expect(readPublicWebPreference(identity)).toEqual({preference: {enabled: true, urls: ''}, failed: false})
  expect(JSON.parse(localStorage.getItem(publicWebPreferenceKey(identity))!)).toEqual({version: 2, enabled: true, urls: '', scope: 'unscoped'})
  expect(parsePublicWebScope(readPublicWebPreference(identity).preference.urls).valid).toBe(false)
  expect(readPublicWebPreference({...identity, conversationId: 'other'}).preference.enabled).toBe(false)
})

it('retains valid v1 bounded consent unchanged and rejects malformed v2 or invalid URL data', () => {
  localStorage.setItem(publicWebPreferenceKey(identity), JSON.stringify({version: 1, enabled: true, urls: 'https://example.org/path'}))
  expect(readPublicWebPreference(identity).preference).toEqual({enabled: true, urls: 'https://example.org/path'})
  for (const value of [{version: 2, enabled: true, urls: '', scope: 'all'}, {version: 2, enabled: true, urls: 'http://example.org', scope: 'unscoped'}, {version: 1, enabled: false, urls: 'http://example.org'}]) {
    localStorage.setItem(publicWebPreferenceKey(identity), JSON.stringify(value))
    expect(readPublicWebPreference(identity).failed).toBe(true)
  }
})

it('persists message-only presentation annotations separately from consent and cannot replay a consumed activation', () => {
  expect(readPublicWebNotice(identity).state).toEqual(emptyPublicWebNotice())
  const state = {activationId: 'activation-1', pending: false, notices: [{activationId: 'activation-1', messageId: 'assistant-1', origins: []}]}
  expect(writePublicWebNotice(identity, state)).toBe(true)
  expect(readPublicWebNotice(identity)).toEqual({state, failed: false})
  expect(readPublicWebPreference(identity).preference.enabled).toBe(false)
  expect(readPublicWebNotice({...identity, conversationId: 'other'}).state.notices).toEqual([])
  writePublicWebNotice(identity, {...state, pending: true})
  expect(readPublicWebNotice(identity).failed).toBe(true)
})
