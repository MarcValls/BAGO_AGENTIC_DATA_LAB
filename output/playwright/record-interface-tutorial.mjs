import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const playwrightModule = 'C:/Users/AMTEC_Terminal_1º/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright/index.mjs'
const { chromium } = await import(pathToFileURL(playwrightModule).href)

const root = process.cwd()
const output = path.join(root, 'output', 'playwright')
const scenes = JSON.parse(fs.readFileSync(path.join(output, 'tutorial-scenes.json'), 'utf8'))
const voiceDir = path.join(os.tmpdir(), 'bago_interface_tutorial_20261012')
const rawDir = path.join(output, 'tutorial-raw-current')
const pauseSeconds = 0.35
const introSilence = 2.2
const audioPath = path.join(voiceDir, 'narration.wav')
const subtitlePath = path.join(output, 'tutorial-interfaz.srt')
const videoPath = path.join(output, 'tutorial-interfaz.webm')

fs.mkdirSync(rawDir, { recursive: true })
if (fs.readdirSync(rawDir).length > 0) {
  throw new Error(`Recording staging folder is not empty; refusing to overwrite: ${rawDir}`)
}

function wavInfo(filename) {
  const data = fs.readFileSync(filename)
  let sampleRate = data.readUInt32LE(24)
  let channels = data.readUInt16LE(22)
  let bits = data.readUInt16LE(34)
  let dataBytes = 0
  for (let offset = 12; offset + 8 <= data.length;) {
    const chunk = data.toString('ascii', offset, offset + 4)
    const size = data.readUInt32LE(offset + 4)
    if (chunk === 'data') { dataBytes = size; break }
    offset += 8 + size + (size % 2)
  }
  const bytesPerSecond = sampleRate * channels * bits / 8
  return { data, sampleRate, channels, bits, dataBytes, duration: dataBytes / bytesPerSecond }
}

const voiceFiles = scenes.map((_, index) => path.join(voiceDir, `scene-${String(index + 1).padStart(2, '0')}.wav`))
const voiceInfo = voiceFiles.map(wavInfo)
const silence = Buffer.alloc(Math.round(voiceInfo[0].sampleRate * voiceInfo[0].channels * voiceInfo[0].bits / 8 * pauseSeconds))
const silenceStart = Buffer.alloc(Math.round(voiceInfo[0].sampleRate * voiceInfo[0].channels * voiceInfo[0].bits / 8 * introSilence))
const audioParts = [silenceStart]
for (let index = 0; index < voiceInfo.length; index += 1) {
  audioParts.push(voiceInfo[index].data.subarray(44, 44 + voiceInfo[index].dataBytes))
  if (index < voiceInfo.length - 1) audioParts.push(silence)
}
const audioHeader = Buffer.from(voiceInfo[0].data.subarray(0, 44))
const audioDataBytes = audioParts.reduce((total, part) => total + part.length, 0)
audioHeader.writeUInt32LE(36 + audioDataBytes, 4)
audioHeader.writeUInt32LE(audioDataBytes, 40)
fs.writeFileSync(audioPath, Buffer.concat([audioHeader, ...audioParts]))

function srtTime(seconds) {
  const millis = Math.round(seconds * 1000)
  const hours = Math.floor(millis / 3_600_000)
  const minutes = Math.floor((millis % 3_600_000) / 60_000)
  const secs = Math.floor((millis % 60_000) / 1000)
  const remainder = millis % 1000
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(remainder).padStart(3, '0')}`
}

function wrapSubtitle(text, width = 46) {
  const lines = []
  let line = ''
  for (const word of text.split(/\s+/)) {
    if (line && `${line} ${word}`.length > width) { lines.push(line); line = word }
    else line = line ? `${line} ${word}` : word
  }
  if (line) lines.push(line)
  return lines.join('\n')
}

let subtitleClock = introSilence
const subtitleBlocks = scenes.map((scene, index) => {
  const start = subtitleClock
  const end = start + voiceInfo[index].duration
  subtitleClock = end + (index < scenes.length - 1 ? pauseSeconds : 0)
  return `${index + 1}\n${srtTime(start)} --> ${srtTime(end)}\n${wrapSubtitle(scene.narration)}\n`
})
fs.writeFileSync(subtitlePath, subtitleBlocks.join('\n'), 'utf8')

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  screen: { width: 1600, height: 900 },
  recordVideo: { dir: rawDir, size: { width: 1600, height: 900 } },
})
const page = await context.newPage()
const blockedWrites = []
await page.route('**/*', async (route) => {
  const request = route.request()
  const method = request.method()
  const url = new URL(request.url())
  if (!['GET', 'HEAD'].includes(method)) {
    blockedWrites.push(`${method} ${url.pathname}`)
    await route.abort()
    return
  }
  if (method === 'GET' && url.pathname === '/api/conversations') {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ conversations: [] }) })
    return
  }
  await route.continue()
})

const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
const recordedVideo = page.video()
await page.goto('http://127.0.0.1:8081/', { waitUntil: 'domcontentloaded', timeout: 20_000 })
await page.waitForTimeout(1_200)

await page.evaluate(() => {
  const cursor = document.createElement('div')
  cursor.setAttribute('aria-hidden', 'true')
  cursor.style.cssText = 'position:fixed;z-index:2147483647;width:16px;height:16px;border:2px solid #f2efea;border-radius:50%;box-shadow:0 0 0 3px rgba(68,123,157,.75);pointer-events:none;transform:translate(-50%,-50%);opacity:0;transition:opacity .12s ease,left .04s linear,top .04s linear'
  document.body.append(cursor)
  document.addEventListener('mousemove', (event) => {
    cursor.style.left = `${event.clientX}px`
    cursor.style.top = `${event.clientY}px`
    cursor.style.opacity = '1'
  })
  document.addEventListener('mouseleave', () => { cursor.style.opacity = '0' })
})

async function navigate(name) {
  await page.getByRole('button', { name, exact: true }).click()
  await page.waitForTimeout(450)
}

async function performAction(action) {
  if (action === 'sidebar') {
    await page.getByRole('button', { name: 'Collapse sidebar' }).click()
    await page.waitForTimeout(550)
    await page.getByRole('button', { name: 'Expand sidebar' }).click()
  } else if (action === 'chat') {
    const agentPanel = page.locator('.chat-agent-panel summary')
    if (!(await agentPanel.evaluate((node) => node.parentElement?.hasAttribute('open')))) await agentPanel.click()
    await page.waitForTimeout(500)
    await page.locator('.control-agent-option').filter({ hasText: 'Frontend Auditor' }).click()
    for (const tabName of ['Archived', 'Trash', 'Recent']) {
      await page.getByRole('button', { name: tabName, exact: true }).click()
      await page.waitForTimeout(250)
    }
  } else if (action === 'composer') {
    const composer = page.locator('#control-chat-input')
    await composer.fill('¿Qué puedo consultar sobre este agente?')
    await composer.press('Shift+Enter')
    await page.keyboard.type('Esta línea no se enviará.')
    await page.waitForTimeout(1_000)
    await composer.fill('')
  } else if (action === 'capabilities') await navigate('Capabilities')
  else if (action === 'builder') {
    await navigate('Agent Builder')
    await page.getByRole('button', { name: /Create Custom Agent/ }).click()
    await page.waitForTimeout(350)
  }
  else if (action === 'runner') await navigate('Agent Runner')
  else if (action === 'evaluation') {
    await navigate('Agent Evaluation Lab')
    await page.waitForTimeout(2_500)
  } else if (action === 'control') await navigate('Control')
  else if (action === 'inspect') {
    await page.getByRole('button', { name: 'Open Inspect' }).click()
    await page.waitForTimeout(900)
    const trace = page.locator('.data-layer-navigation .navigation-item').filter({ hasText: 'Trace' })
    if (await trace.count()) { await trace.click(); await page.waitForTimeout(500) }
  } else if (action === 'settings') {
    await page.getByRole('button', { name: 'Back to Workspace' }).click()
    await page.getByRole('button', { name: 'Open settings' }).click()
    await page.waitForTimeout(700)
  } else if (action === 'closing') {
    await page.keyboard.press('Escape')
    await navigate('Chat')
  }
}

await page.waitForTimeout(introSilence * 1000 - 1_200)
for (let index = 0; index < scenes.length; index += 1) {
  const sceneStartedAt = Date.now()
  await performAction(scenes[index].action)
  const hold = voiceInfo[index].duration + (index < scenes.length - 1 ? pauseSeconds : 0)
  const remaining = hold * 1000 - (Date.now() - sceneStartedAt)
  if (remaining > 0) await page.waitForTimeout(remaining)
}

await context.close()
await browser.close()
const rawVideoPath = await recordedVideo.path()
fs.copyFileSync(rawVideoPath, videoPath)
console.log(JSON.stringify({
  videoPath,
  audioPath,
  subtitlePath,
  expectedDurationSeconds: subtitleClock,
  blockedWrites,
  pageErrors,
}, null, 2))
