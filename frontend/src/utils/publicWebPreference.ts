import {parsePublicWebScope} from './publicWebUrls'

export type PublicWebIdentity = {projectId: string; root: string; ownerKind: 'assistant' | 'agent'; ownerId: string; conversationId: string}
export type PublicWebPreference = {enabled: boolean; urls: string}
const PREFIX = 'bago.public-web.conversation.v1:'
const EMPTY: PublicWebPreference = {enabled: false, urls: ''}
type Store = Pick<Storage, 'getItem' | 'setItem'>

export function publicWebPreferenceKey(identity: PublicWebIdentity): string {
  return PREFIX + JSON.stringify([identity.projectId, identity.root, identity.ownerKind, identity.ownerId, identity.conversationId])
}

export function readPublicWebPreference(identity: PublicWebIdentity, storage?: Store): {preference: PublicWebPreference; failed: boolean} {
  try {
    const raw = (storage ?? window.localStorage).getItem(publicWebPreferenceKey(identity))
    if (raw === null) return {preference: {...EMPTY}, failed: false}
    const value = JSON.parse(raw)
    const scope = typeof value?.urls === 'string' ? parsePublicWebScope(value.urls) : null
    const unscoped = value?.version === 2 && value.enabled === true && value.urls === '' && value.scope === 'unscoped'
      && Object.keys(value).sort().join(',') === 'enabled,scope,urls,version'
    const bounded = value?.version === 1 && typeof value.enabled === 'boolean' && typeof value.urls === 'string'
      && value.urls.length <= 16384 && Object.keys(value).sort().join(',') === 'enabled,urls,version'
      && (scope?.valid || (!value.enabled && value.urls === ''))
    if (!unscoped && !bounded) throw new Error('Invalid preference')
    return {preference: {enabled: value.enabled, urls: value.urls}, failed: false}
  } catch { return {preference: {...EMPTY}, failed: true} }
}

export function writePublicWebPreference(identity: PublicWebIdentity, preference: PublicWebPreference, storage?: Store): boolean {
  try {
    // Explicit empty ON is preference only. Invalid nonempty input still persists OFF.
    const valid = parsePublicWebScope(preference.urls).valid
    const value = preference.enabled && preference.urls === ''
      ? {version: 2, enabled: true, urls: '', scope: 'unscoped'}
      : {version: 1, enabled: preference.enabled && valid, urls: valid ? preference.urls : ''}
    ;(storage ?? window.localStorage).setItem(publicWebPreferenceKey(identity), JSON.stringify(value))
    return true
  } catch { return false }
}

export type PublicWebNotice = {activationId: string; messageId: string; origins: string[]}
export type PublicWebNoticeState = {activationId: string|null; pending: boolean; notices: PublicWebNotice[]}
export const emptyPublicWebNotice = (): PublicWebNoticeState => ({activationId: null, pending: false, notices: []})
const noticeKey = (identity: PublicWebIdentity) => publicWebPreferenceKey(identity) + ':notice.v1'

/** Presentation annotations only: no token, message text, grant or backend history mutation. */
export function readPublicWebNotice(identity: PublicWebIdentity, storage?: Store): {state: PublicWebNoticeState; failed: boolean} {
  try {
    const raw = (storage ?? window.localStorage).getItem(noticeKey(identity))
    if (raw === null) return {state: emptyPublicWebNotice(), failed: false}
    const value = JSON.parse(raw)
    if (value?.version !== 1 || !Array.isArray(value.notices) || typeof value.pending !== 'boolean'
        || !(value.activationId === null || typeof value.activationId === 'string' && value.activationId.length > 0)
        || value.pending && !value.activationId || Object.keys(value).sort().join(',') !== 'activationId,notices,pending,version') throw new Error('Invalid notice')
    const activations = new Set<string>()
    for (const notice of value.notices) {
      if (!notice || typeof notice.activationId !== 'string' || !notice.activationId || activations.has(notice.activationId)
          || typeof notice.messageId !== 'string' || !notice.messageId || !Array.isArray(notice.origins)
          || notice.origins.some((origin: unknown) => typeof origin !== 'string' || !parsePublicWebScope(origin).valid || new URL(origin).origin !== origin)
          || Object.keys(notice).sort().join(',') !== 'activationId,messageId,origins') throw new Error('Invalid annotation')
      activations.add(notice.activationId)
    }
    if (value.pending && activations.has(value.activationId)) throw new Error('Already consumed activation')
    return {state: {activationId: value.activationId, pending: value.pending, notices: value.notices}, failed: false}
  } catch {return {state: emptyPublicWebNotice(), failed: true}}
}

export function writePublicWebNotice(identity: PublicWebIdentity, state: PublicWebNoticeState, storage?: Store): boolean {
  try {
    ;(storage ?? window.localStorage).setItem(noticeKey(identity), JSON.stringify({version: 1, ...state}))
    return true
  } catch {return false}
}
