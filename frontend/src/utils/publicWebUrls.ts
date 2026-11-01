/** Message URLs are data, never consent. Backend performs the public-address checks. */
export function publicHttpsUrl(value: string): string | undefined {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && !url.port ? url.href : undefined
  } catch { return undefined }
}

export function parsePublicWebScope(text: string): {urls: string[]; origins: string[]; valid: boolean} {
  const entries = [...new Set(text.split(/\r?\n/).map(value => value.trim()).filter(Boolean))]
  const urls = entries.map(publicHttpsUrl)
  const valid = entries.length > 0 && entries.length <= 8 && urls.every((url): url is string => Boolean(url))
  const normalized = [...new Set(urls.filter((url): url is string => Boolean(url)))]
  return {urls: normalized, origins: [...new Set(normalized.map(url => new URL(url).origin))], valid}
}

// Ported surgically from the earlier dirty-root usability repair; not from model output.
export function extractPublicHttpsUrls(message: string): {urls: string[]; invalid: boolean} {
  const candidates = message.match(/https?:\/\/[^\s<>"'`]+/gi) ?? []
  const urls: string[] = []
  let invalid = false
  for (const candidate of candidates) {
    let value = candidate.replace(/[.,!?;:]+$/g, '')
    for (const [open, close] of [['(', ')'], ['[', ']'], ['{', '}']]) {
      while (value.endsWith(close) && [...value].filter(char => char === close).length > [...value].filter(char => char === open).length) value = value.slice(0, -1)
    }
    const safe = publicHttpsUrl(value)
    if (!safe) { invalid = true; continue }
    if (!urls.includes(safe)) urls.push(safe)
  }
  return {urls, invalid}
}
