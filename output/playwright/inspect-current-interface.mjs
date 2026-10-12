import { pathToFileURL } from 'node:url'
const { chromium } = await import(pathToFileURL('C:/Users/AMTEC_Terminal_1º/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright/index.mjs').href)
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } })
const page = await context.newPage()
await page.route('**/*', async route => {
  if (!['GET', 'HEAD'].includes(route.request().method())) return route.abort()
  const url = new URL(route.request().url())
  if (url.pathname === '/api/conversations') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"conversations":[]}' })
  return route.continue()
})
await page.goto('http://127.0.0.1:8081/', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1500)
const summarize = async label => {
  const text = await page.locator('body').innerText()
  const buttons = await page.getByRole('button').allTextContents()
  console.log(`\n--- ${label} ---\n${text.slice(0, 2400)}\nBUTTONS: ${buttons.map(x => x.trim()).filter(Boolean).join(' | ')}`)
}
await summarize('initial')
await page.getByRole('button', { name: 'Open Inspect' }).click().catch(() => {})
await page.waitForTimeout(700)
await summarize('Inspect')
await page.keyboard.press('Escape')
await page.getByRole('button', { name: 'Open settings' }).click().catch(() => {})
await page.waitForTimeout(700)
await summarize('Settings')
await page.keyboard.press('Escape')
await page.getByRole('button', { name: 'Chat', exact: true }).click()
await page.waitForTimeout(300)
await summarize('Chat')
for (const name of ['Capabilities', 'Agent Builder', 'Agent Runner', 'Agent Evaluation Lab', 'Control']) {
  const button = page.getByRole('button', { name, exact: true })
  if (await button.count()) { await button.click(); await page.waitForTimeout(name === 'Agent Evaluation Lab' ? 3500 : 700); await summarize(name) }
}
await browser.close()
