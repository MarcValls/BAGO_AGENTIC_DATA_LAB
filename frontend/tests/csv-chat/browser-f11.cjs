/*
 * F11 real-browser reproduction. Requires a running ADL API/UI, a project with
 * the historical CSV and saved READ, and an explicitly labelled controlled
 * interpretation provider. It never intercepts HTTP or creates fake grants.
 *
 * ADL_PLAYWRIGHT_MODULE=/absolute/path/to/playwright
 * ADL_EVIDENCE_DIR=/absolute/output/directory node browser-f11.cjs [desktop mobile]
 *
 * This is deliberately separate from Vitest's mocked transport tests. The
 * provider fixture is not evidence of a live AI model or a Windows execution.
 */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const {createHash} = require('node:crypto')
const {chromium} = require(process.env.ADL_PLAYWRIGHT_MODULE || 'playwright')

const url = process.env.ADL_URL || 'http://127.0.0.1:5173'
const output = process.env.ADL_EVIDENCE_DIR
assert(output && path.isAbsolute(output), 'Set ADL_EVIDENCE_DIR to an absolute output directory')
const csvPath = process.env.ADL_CSV_PATH || 'demo-usuario/archivo/pedidos-final.csv'
const question = 'Analiza pedidos: importe descontado por pedido, pendientes por estado y total general.'
const sourceSha = '8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5'
const viewports = {desktop: {width: 1440, height: 1000}, mobile: {width: 390, height: 844}}
const modes = process.argv.slice(2).length ? process.argv.slice(2) : ['desktop', 'mobile']
const repo = path.resolve(__dirname, '../../..')
const files = [
  'frontend/src/components/AgentChat.tsx',
  'frontend/src/components/ChatTools.tsx',
  'frontend/src/components/AgentChatOverrides.css',
  'frontend/src/components/CsvChatQuery.tsx',
  'frontend/src/components/CsvChatQuery.css',
  'frontend/src/types/csvChat.ts',
  'frontend/src/i18n/index.ts',
  'frontend/src/i18n/domains/csvChat.ts',
  'frontend/tests/csv-chat/main-chat-csv.test.tsx',
  'frontend/tests/csv-chat/browser-f11.cjs',
  'src/agent_tools/workspace_read.py',
  'src/agent_tools/csv_chat.py',
  'src/api/server.py',
  'src/api/schemas.py',
  'tools/document-toolkit/document_toolkit/parsers.py',
  'tools/document-toolkit/document_toolkit/csv_query.py',
]
function sha256(bytes) {return createHash('sha256').update(bytes).digest('hex')}
function databaseSnapshot(filename) {
  assert(path.isAbsolute(filename), 'Runtime storage must identify its actual SQLite file')
  const stat = fs.statSync(filename, {bigint: true})
  return {path: filename, inode: String(stat.ino), device: String(stat.dev), size: String(stat.size), mtime_ns: String(stat.mtimeNs), sha256: sha256(fs.readFileSync(filename))}
}
function sanitized(value) {
  if (Array.isArray(value)) return value.map(sanitized)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, val]) => [key, /authorization_id/.test(key) ? '[REDACTED]' : sanitized(val)]))
  return value
}
fs.mkdirSync(output, {recursive: true})

async function run() {
  const browser = await chromium.launch({headless: true})
  try {
    for (const mode of modes) {
      assert(viewports[mode], `Unknown viewport ${mode}`)
      assert(!fs.existsSync(path.join(output, `${mode}.json`)), 'Use a fresh evidence directory; historical runs must remain unchanged')
      const evidence = {
        case: 'F11', mode, url, viewport: viewports[mode], browser: browser.version(),
        started_at: new Date().toISOString(),
        verification: 'CONTROLLED_INTERPRETATION_REAL_BACKEND',
        source_binding_note: 'Hashes record the working tree at invocation. A running server may predate these files; bind final evidence to a fresh server launch separately.',
        request: {message: question, csv_read: {path: csvPath, delimiter: 'auto', decimal_separator: '.'}},
        source_files_sha256: Object.fromEntries(files.map(file => [file, sha256(fs.readFileSync(path.join(repo, file)))])),
        page_errors: [], console_errors: [], mutations: [], status: 'RUNNING',
      }
      const page = await browser.newPage({viewport: viewports[mode]})
      page.on('pageerror', error => evidence.page_errors.push(error.message))
      page.on('console', message => {if (message.type() === 'error') evidence.console_errors.push(message.text())})
      page.on('request', request => {
        if (request.method() === 'GET' || !request.url().includes('/api/')) return
        const pathname = new URL(request.url()).pathname
        if (pathname === '/api/project-permissions/directories') return
        let body = null
        try {body = request.postDataJSON()} catch {}
        evidence.mutations.push({method: request.method(), path: pathname.replace(/(\/authorizations\/)[^/]+$/, '$1[REDACTED]'), body: sanitized(body)})
      })
      try {
        await page.goto(url, {waitUntil: 'networkidle'})
        const storageUrl = new URL('/api/runtime/storage', url).href
        const storageResponse = await page.request.get(storageUrl)
        assert.equal(storageResponse.status(), 200)
        evidence.runtime_storage_before = await storageResponse.json()
        assert.equal(evidence.runtime_storage_before.server_source_sha256_at_import, evidence.source_files_sha256['src/api/server.py'])
        if (process.env.ADL_EXPECTED_DATA_ROOT) assert.equal(evidence.runtime_storage_before.data_root, process.env.ADL_EXPECTED_DATA_ROOT)
        evidence.database_before = databaseSnapshot(evidence.runtime_storage_before.effective_paths.conversations)
        await page.getByRole('button', {name: 'Nueva', exact: true}).click()
        const closeProject = page.getByRole('button', {name: 'Cerrar panel de Proyecto'})
        if (await closeProject.isVisible()) await closeProject.click()
        await page.getByText('Recursos', {exact: true}).click()
        await page.getByRole('button', {name: 'Consultar archivo', exact: true}).click()
        const dialog = page.getByRole('dialog', {name: 'Consultar archivo'})
        for (const directory of csvPath.split('/').slice(0, -1)) {
          await dialog.getByRole('button', {name: `Abrir carpeta ${directory}`, exact: true}).click()
        }
        await dialog.getByRole('button', {name: `Seleccionar ${csvPath}`, exact: true}).click()
        await dialog.getByLabel('Pregunta sobre este CSV', {exact: true}).fill(question)
        const submit = dialog.getByRole('button', {name: 'Autorizar y consultar en el chat', exact: true})
        assert(await submit.isDisabled(), 'Consent must be explicit before sending')
        assert(!evidence.mutations.some(item => item.path === '/api/workspace-read/authorizations'), 'Selecting metadata cannot grant a read')
        await page.screenshot({path: path.join(output, `${mode}-selection.png`), fullPage: true})
        evidence.selection_overflow = await dialog.evaluate(element => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth}))
        await dialog.getByLabel('Autorizo la lectura de este CSV para esta pregunta y estas opciones.', {exact: true}).check()
        const chatResponse = page.waitForResponse(response => response.url().endsWith('/api/chat/control') && response.request().method() === 'POST')
        await submit.click()
        const response = await chatResponse
        evidence.http_status = response.status()
        evidence.response = sanitized(await response.json())
        assert.equal(response.status(), 200)
        assert.equal(evidence.response.csv_analysis.status, 'answered')
        assert.equal(evidence.response.csv_analysis.file_sha256, sourceSha)
        assert.equal(evidence.response.csv_analysis.coverage.total_rows, 3)
        assert.equal(evidence.response.csv_analysis.coverage.matched_rows, 3)
        assert.equal(evidence.response.csv_analysis.coverage.complete_input, true)
        assert.equal(Number(evidence.response.csv_analysis.grand_totals.values.total), 301.30)
        await dialog.waitFor({state: 'hidden'})
        await page.getByLabel('Archivos del proyecto consultados').last().waitFor()
        assert(await page.getByLabel('Archivos del proyecto consultados').last().textContent().then(text => text.includes(sourceSha)))
        await page.screenshot({path: path.join(output, `${mode}-result.png`), fullPage: true})
        const evidencePanel = page.getByLabel('Evidencia de la consulta CSV').last()
        await evidencePanel.locator('summary').click()
        await evidencePanel.scrollIntoViewIfNeeded()
        await page.screenshot({path: path.join(output, `${mode}-provenance.png`), fullPage: true})
        const grantCalls = evidence.mutations.filter(item => item.path === '/api/workspace-read/authorizations')
        const chatCalls = evidence.mutations.filter(item => item.path === '/api/chat/control')
        assert.equal(grantCalls.length, 1)
        assert.equal(chatCalls.length, 1)
        assert.deepEqual(grantCalls[0].body.csv_request, evidence.request)
        assert.deepEqual(chatCalls[0].body.csv_read, evidence.request.csv_read)
        assert(!evidence.mutations.some(item => /knowledge|document|web-read/.test(item.path)))
        assert.equal(evidence.page_errors.length, 0)
        assert.equal(evidence.console_errors.length, 0)
        // Main chat deliberately starts blank (historySelection=explicit). Reopen
        // the exact persisted conversation instead of assuming automatic history.
        await page.reload({waitUntil: 'networkidle'})
        const conversationId = evidence.response.conversation.id
        const readConversation = page.waitForResponse(response => response.request().method() === 'GET' && new URL(response.url()).pathname === `/api/conversations/${conversationId}`)
        await page.locator(`[data-conversation-id="${conversationId}"]:visible`).getByRole('button').first().click()
        const persistedResponse = await readConversation
        evidence.reload_http_status = persistedResponse.status()
        evidence.reload_conversation = sanitized(await persistedResponse.json())
        assert.equal(evidence.reload_http_status, 200)
        assert.equal(evidence.reload_conversation.id, conversationId)
        assert.equal(evidence.reload_conversation.revision, evidence.response.conversation.revision)
        const savedAssistant = evidence.response.conversation.messages.filter(message => message.role === 'assistant').at(-1)
        const reopenedAssistant = evidence.reload_conversation.messages.find(message => message.id === savedAssistant.id)
        assert(reopenedAssistant, 'The exact assistant message must survive server persistence')
        assert.deepEqual(reopenedAssistant.references.csv_analysis, evidence.response.csv_analysis)
        assert.deepEqual(reopenedAssistant.references.sources, evidence.response.sources)
        assert.deepEqual(reopenedAssistant.references.read_events, evidence.response.read_events)
        evidence.persisted_after_reload = true
        evidence.reopened_conversation_id = conversationId
        const reopenedArticle = page.locator(`[aria-labelledby="message-author-${savedAssistant.id}"]`)
        await reopenedArticle.waitFor({state: 'attached'})
        if (await closeProject.isVisible()) await closeProject.click()
        await reopenedArticle.waitFor()
        await page.getByLabel('Archivos del proyecto consultados').last().waitFor()
        assert(await page.getByLabel('Archivos del proyecto consultados').last().textContent().then(text => text.includes(sourceSha)))
        evidence.rendered_after_reload = true
        const storageAfter = await page.request.get(storageUrl)
        assert.equal(storageAfter.status(), 200)
        evidence.runtime_storage_after = await storageAfter.json()
        assert.equal(evidence.runtime_storage_after.process_id, evidence.runtime_storage_before.process_id)
        assert.equal(evidence.runtime_storage_after.server_source_sha256_at_import, evidence.source_files_sha256['src/api/server.py'])
        evidence.database_after = databaseSnapshot(evidence.runtime_storage_after.effective_paths.conversations)
        assert.equal(evidence.database_after.path, evidence.database_before.path)
        assert.equal(evidence.database_after.inode, evidence.database_before.inode, 'The SQLite file must not be replaced during a run')
        assert.equal(evidence.database_after.device, evidence.database_before.device)
        assert(BigInt(evidence.database_after.mtime_ns) >= BigInt(evidence.database_before.mtime_ns), 'The SQLite file mtime must not roll back')
        evidence.status = 'PASS'
      } catch (error) {
        evidence.status = 'FAIL'
        evidence.error = String(error.stack || error)
        await page.screenshot({path: path.join(output, `${mode}-failure.png`), fullPage: true}).catch(() => {})
        throw error
      } finally {
        evidence.finished_at = new Date().toISOString()
        fs.writeFileSync(path.join(output, `${mode}.json`), JSON.stringify(evidence, null, 2) + '\n')
        console.log(JSON.stringify({mode, status: evidence.status, http_status: evidence.http_status, conversation_id: evidence.response?.conversation?.id, page_errors: evidence.page_errors, console_errors: evidence.console_errors, evidence: path.join(output, `${mode}.json`)}))
        await page.close()
      }
    }
  } finally {await browser.close()}
}
run().catch(error => {console.error(error); process.exitCode = 1})
