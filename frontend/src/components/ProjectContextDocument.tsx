import { Fragment, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type ContextLocation = { id: string; label: string; path: string; state: 'present' | 'absent'; purpose: string }
type Document = { id: string; workspace_root: string; path: string; format: 'json' | 'markdown'; content: string; size_bytes: number; sha256: string }

function InlineText({ text }: { text: string }) {
  return <>{text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, i) => part.startsWith('`')
    ? <code key={i}>{part.slice(1, -1)}</code> : part.startsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>)}</>
}

function MarkdownBlocks({ lines }: { lines: string[] }) {
  const blocks: ReactNode[] = []
  for (let i = 0; i < lines.length;) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    const fence = line.match(/^\s*(`{3,}|~{3,})/)
    if (fence) {
      const code: string[] = []
      i++
      while (i < lines.length && !lines[i].trimStart().startsWith(fence[1])) code.push(lines[i++])
      i++
      blocks.push(<pre key={i}><code>{code.join('\n')}</code></pre>)
      continue
    }
    const list = line.match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)/)
    if (list) {
      const items: string[] = []
      const ordered = !list[1]
      while (i < lines.length) {
        const item = lines[i].match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)/)
        if (!item || !item[1] !== ordered) break
        items.push(item[2]); i++
      }
      const children = items.map((item, index) => <li key={index}><InlineText text={item} /></li>)
      blocks.push(ordered ? <ol key={i}>{children}</ol> : <ul key={i}>{children}</ul>)
      continue
    }
    const paragraph: string[] = [line]
    i++
    while (i < lines.length && lines[i].trim() && !/^\s*(`{3,}|~{3,}|[-*+]\s|\d+[.)]\s)/.test(lines[i])) paragraph.push(lines[i++])
    blocks.push(<p key={i}><InlineText text={paragraph.join('\n')} /></p>)
  }
  return <>{blocks}</>
}

function MarkdownDocument({ content }: { content: string }) {
  const sections: { title: string; lines: string[] }[] = []
  let section = { title: '', lines: [] as string[] }
  let fence = ''
  for (const line of content.split(/\r?\n/)) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)
    if (marker) { if (!fence) fence = marker[1]; else if (marker[1].startsWith(fence)) fence = '' }
    const heading = !fence && line.match(/^#{1,6}\s+(.+?)\s*#*$/)
    if (heading) {
      if (section.title || section.lines.some(text => text.trim())) sections.push(section)
      section = { title: heading[1], lines: [] }
    } else section.lines.push(line)
  }
  if (section.title || section.lines.some(text => text.trim())) sections.push(section)
  if (sections.length === 0) return <p>El archivo está vacío.</p>
  return <div className="project-document-markdown">{sections.map((item, i) => item.title
    ? <details className="project-document-section" key={i} open><summary><InlineText text={item.title} /></summary><MarkdownBlocks lines={item.lines} /></details>
    : <div key={i}><MarkdownBlocks lines={item.lines} /></div>)}</div>
}

function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || typeof value !== 'object') return <span className={`project-json-${typeof value}`}>{value === null ? 'null' : String(value)}</span>
  if (depth >= 12) return <span>Estructura profunda. Consulta el texto original.</span>
  const entries = Object.entries(value)
  if (entries.length === 0) return <code>{Array.isArray(value) ? '[]' : '{}'}</code>
  return <dl className="project-json-tree">{entries.map(([key, child]) => <div key={key}>
    <dt>{Array.isArray(value) ? `Elemento ${Number(key) + 1}` : key}</dt>
    <dd>{child !== null && typeof child === 'object'
      ? <details className="project-document-section" open={depth < 1}><summary>{Array.isArray(child) ? 'Lista' : 'Objeto'} · {Object.keys(child).length} campos</summary><JsonValue value={child} depth={depth + 1} /></details>
      : <JsonValue value={child} depth={depth + 1} />}</dd>
  </div>)}</dl>
}

function StructuredDocument({ document }: { document: Document }) {
  if (document.format === 'markdown') return <MarkdownDocument content={document.content} />
  let parsed: unknown
  try { parsed = JSON.parse(document.content) }
  catch { return <><p role="alert">El JSON no es válido. Puedes revisar el texto original.</p><pre>{document.content}</pre></> }
  return <JsonValue value={parsed} />
}

export default function ProjectContextDocument({ item, workspaceRoot }: { item: ContextLocation; workspaceRoot: string }) {
  const [expanded, setExpanded] = useState(false)
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [missing, setMissing] = useState(item.state === 'absent')
  const [request, setRequest] = useState(0)

  useEffect(() => {
    if (!expanded) return
    const controller = new AbortController()
    setLoading(true); setDocument(null); setError('')
    void fetch(`/api/chat/context/document/${encodeURIComponent(item.id)}?workspace_root=${encodeURIComponent(workspaceRoot)}`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const body = await response.json()
        if (controller.signal.aborted) return
        if (!response.ok) { setMissing(body.detail?.code === 'document_not_found'); throw new Error(body.detail?.message || 'No se pudo cargar el archivo.') }
        if (body.id !== item.id || body.workspace_root !== workspaceRoot || typeof body.content !== 'string' || !['markdown', 'json'].includes(body.format)) throw new Error('El documento no corresponde al proyecto seleccionado.')
        setDocument(body as Document); setMissing(false)
      }).catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'No se pudo cargar el archivo.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [expanded, request, workspaceRoot, item.id])

  return <details className={`workspace-source project-document ${missing ? 'absent' : 'present'}`} onToggle={event => { if (event.target === event.currentTarget) setExpanded(event.currentTarget.open) }}>
    <summary><strong>{item.label}</strong><span>{missing ? 'No encontrado' : 'Disponible'}</span></summary>
    <code className="project-document-path" title={item.path}>{item.path}</code>
    {expanded && <div className="project-document-content">
      <div className="project-document-toolbar"><span>Vista de lectura</span><button type="button" disabled={loading} onClick={() => setRequest(value => value + 1)}>Actualizar</button></div>
      {loading && <p role="status">Leyendo archivo…</p>}
      {error && <p role={missing ? 'status' : 'alert'}>{error}</p>}
      {document && <><StructuredDocument document={document} /><details className="project-document-raw"><summary>Texto original</summary><pre>{document.content}</pre></details></>}
    </div>}
  </details>
}
