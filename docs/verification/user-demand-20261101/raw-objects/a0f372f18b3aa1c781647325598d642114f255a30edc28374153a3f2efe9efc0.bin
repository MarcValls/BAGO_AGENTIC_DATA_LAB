/** Read-only RFC-style CSV/TSV preview. Never serializes or normalizes the editor text. */
export const PREVIEW_ROWS = 200
export const PREVIEW_COLUMNS = 50
export const PREVIEW_CHARACTERS = 200_000
export type DelimitedError = 'unclosed_quote' | 'unexpected_quote' | 'after_quote'
export type DelimitedPreview = {rows: string[][]; truncated: boolean; ragged: boolean; error: DelimitedError | null}

export function delimitedFile(path: string): ',' | '\t' | null {
  return /\.csv$/i.test(path) ? ',' : /\.tsv$/i.test(path) ? '\t' : null
}

export function parseDelimitedPreview(text: string, delimiter: ',' | '\t' = ','): DelimitedPreview {
  const rows: string[][] = []
  let row: string[] = [], field = '', quoted = false, closedQuote = false, endedRow = true
  let truncated = false
  const end = Math.min(text.length, PREVIEW_CHARACTERS)
  const fail = (error: DelimitedError): DelimitedPreview => ({rows: [], truncated: false, ragged: false, error})
  const finishField = () => { row.push(field); field = ''; closedQuote = false }
  for (let i = text.charCodeAt(0) === 0xfeff ? 1 : 0; i < end; i++) {
    const character = text[i]
    if (quoted) {
      if (character === '"') {
        if (text[i + 1] === '"' && i + 1 < end) { field += '"'; i++ }
        else { quoted = false; closedQuote = true }
      } else field += character
      endedRow = false
      continue
    }
    if (character === delimiter) { finishField(); endedRow = false }
    else if (character === '\r' || character === '\n') {
      if (character === '\r' && text[i + 1] === '\n') i++
      finishField(); rows.push(row); row = []; endedRow = true
      if (rows.length >= PREVIEW_ROWS + 1 && i + 1 < text.length) { truncated = true; break }
    } else if (closedQuote) return fail('after_quote')
    else if (character === '"') {
      if (field !== '') return fail('unexpected_quote')
      quoted = true; endedRow = false
    } else { field += character; endedRow = false }
  }
  if (text.length > end) truncated = true
  if (!truncated) {
    if (quoted) return fail('unclosed_quote')
    if (!endedRow) { finishField(); rows.push(row) }
  }
  const width = rows[0]?.length ?? 0
  const ragged = rows.some(record => record.length !== width)
  if (rows.some(record => record.length > PREVIEW_COLUMNS)) truncated = true
  return {rows: rows.map(record => record.slice(0, PREVIEW_COLUMNS)), truncated, ragged, error: null}
}
