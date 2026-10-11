const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('C:/Users/AMTEC_Terminal_1º/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright')

const root = __dirname
const audio = JSON.parse(fs.readFileSync(path.join(root, 'audio/metadata.json'), 'utf8').replace(/^\uFEFF/, ''))
const captureDir = path.join(root, 'capture/raw')
fs.mkdirSync(captureDir, { recursive: true })

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1,
    recordVideo: { dir: captureDir, size: { width: 1600, height: 900 } },
  })
  const page = await context.newPage()
  const runtimeStart = Date.now()
  const scenes = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))

  const caption = async (text) => page.evaluate((value) => {
    let el = document.getElementById('tutorial-caption')
    if (!el) {
      el = document.createElement('div')
      el.id = 'tutorial-caption'
      Object.assign(el.style, {
        position: 'fixed', left: '4%', bottom: '92px', width: '92%', zIndex: '2147483000',
        boxSizing: 'border-box', padding: '14px 22px', borderRadius: '12px',
        background: 'rgba(5, 13, 27, 0.94)', color: '#fff', border: '1px solid #6da5e8',
        boxShadow: '0 4px 24px rgba(0,0,0,.5)', textAlign: 'center',
        font: '600 23px/1.35 Segoe UI, Arial, sans-serif', pointerEvents: 'none',
      })
      document.body.appendChild(el)
    }
    el.textContent = value
  }, text)
  const clearCaption = async () => page.evaluate(() => document.getElementById('tutorial-caption')?.remove())
  const begin = (id) => ({ id, start_ms: Date.now() - runtimeStart })
  const finish = async (mark) => {
    const item = audio.find(row => row.id === mark.id)
    const target = item.duration * 1000 + 250
    const elapsed = Date.now() - runtimeStart - mark.start_ms
    if (elapsed < target) await page.waitForTimeout(target - elapsed)
    scenes.push({ ...mark, end_ms: Date.now() - runtimeStart, narration_id: mark.id })
    await clearCaption()
  }
  const speakScene = async (id, action) => {
    const item = audio.find(row => row.id === id)
    await caption(item.text)
    const mark = begin(id)
    await action()
    await finish(mark)
  }

  try {
    await page.goto('http://127.0.0.1:8081/', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.getByRole('heading', { name: 'Agentic Data Lab' }).waitFor({ timeout: 20000 })
    await page.waitForTimeout(1200)

    await speakScene('01_intro', async () => {})

    await speakScene('02_agents', async () => {
      const suggestion = page.getByRole('button', { name: 'List my agents' })
      if (await suggestion.count()) await suggestion.click()
      else await page.locator('#control-chat-input').fill('Lista mis agentes')
      await page.getByRole('button', { name: 'Send' }).click()
      await page.locator('.control-chat-messages article').nth(1).waitFor({ state: 'visible', timeout: 20000 })
    })

    await page.getByRole('button', { name: 'Provider settings' }).click()
    const keyField = page.locator('#ollama-api-key')
    await keyField.waitFor({ timeout: 15000 })
    const settingsZoom = 0.66
    await page.evaluate((zoom) => { document.documentElement.style.zoom = String(zoom) }, settingsZoom)
    await keyField.scrollIntoViewIfNeeded()
    const bounds = await keyField.boundingBox()
    if (!bounds) throw new Error('Credential field not visible; refusing to record the settings screen.')
    await page.evaluate(({ box, zoom }) => {
      const mask = document.createElement('div')
      mask.id = 'tutorial-credential-mask'
      Object.assign(mask.style, {
        position: 'fixed', left: `${box.x / zoom}px`, top: `${box.y / zoom}px`, width: `${box.width / zoom}px`, height: `${box.height / zoom}px`,
        zIndex: '2147483646', background: '#101b2b', border: '2px solid #7faee8', borderRadius: '7px',
        display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#eef6ff',
        font: '700 15px Segoe UI, Arial, sans-serif', letterSpacing: '1px', pointerEvents: 'none',
      })
      mask.textContent = 'CREDENCIAL CENSURADA'
      document.body.appendChild(mask)
    }, { box: bounds, zoom: settingsZoom })
    await speakScene('03_provider', async () => {})

    await page.getByRole('button', { name: 'Chat', exact: true }).click()
    await page.evaluate(() => { document.getElementById('tutorial-credential-mask')?.remove(); document.documentElement.style.zoom = '1' })
    await page.getByRole('button', { name: /Frontend Auditor tool/ }).click()
    const readPrompt = 'Lee output/tutorial/sample-note.txt y resume sus dos ideas principales en dos viñetas.'
    await speakScene('04_read', async () => {
      await page.getByRole('checkbox', { name: /Allow read-only project files/ }).check()
      await page.locator('#control-chat-input').fill(readPrompt)
      await page.getByRole('button', { name: 'Send' }).click()
      await page.locator('.muted-state').waitFor({ state: 'visible', timeout: 10000 })
    })
    await page.getByText('Project files read', { exact: true }).waitFor({ state: 'visible', timeout: 180000 })
    await speakScene('05_receipt', async () => {})

    await page.getByRole('button', { name: /App assistant/ }).click()
    const createSuggestion = page.getByRole('button', { name: 'Create an agent' })
    await createSuggestion.waitFor({ state: 'visible', timeout: 10000 })
    await speakScene('06_draft', async () => {
      await createSuggestion.click()
      await page.locator('#control-chat-input').fill('Quiero crear un agente que resuma informes que el usuario pegue en el chat. No debe modificar archivos ni ejecutar acciones.')
      await page.getByRole('button', { name: 'Send' }).click()
      await page.locator('.muted-state').waitFor({ state: 'visible', timeout: 10000 })
    })
    await page.locator('.agent-draft-card').waitFor({ state: 'visible', timeout: 180000 })
    await speakScene('07_review', async () => {})

    await speakScene('08_cancel', async () => {
      await page.getByRole('button', { name: 'Cancel proposal' }).click()
      await page.getByText('Proposal cancelled. No agent was created.', { exact: true }).waitFor({ state: 'visible', timeout: 10000 })
    })

    await page.getByRole('button', { name: 'Agent Builder', exact: true }).click()
    await page.waitForTimeout(800)
    await speakScene('09_builder', async () => {})
    await speakScene('10_outro', async () => {})
  } catch (error) {
    errors.push(error.stack || String(error))
  } finally {
    await context.close()
    const videoPath = await page.video().path()
    const finalRaw = path.join(captureDir, 'adl-first-user-tutorial-source.webm')
    if (videoPath !== finalRaw) fs.copyFileSync(videoPath, finalRaw)
    fs.writeFileSync(path.join(root, 'capture/scenes.json'), JSON.stringify({ scenes, errors, source_video: 'raw/adl-first-user-tutorial-source.webm' }, null, 2))
    await browser.close()
    if (errors.length) {
      console.error(errors.join('\n\n'))
      process.exitCode = 1
    } else {
      console.log(JSON.stringify({ scenes, source_video: finalRaw }, null, 2))
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
