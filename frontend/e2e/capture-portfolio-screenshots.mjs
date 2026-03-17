import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://127.0.0.1:4173'
const API_URL = process.env.API_URL || 'http://127.0.0.1:8000/api/v1'
const outputDir = path.resolve(__dirname, '../../assets/screenshots')

async function ensureDemoAuth() {
  const suffix = Date.now().toString().slice(-8)
  const payload = {
    username: `portfolio_${suffix}`,
    password: 'portfolio123',
    email: `portfolio_${suffix}@example.com`,
    real_name: 'Portfolio Demo',
    phone: '+852 0000 0000',
    github: 'https://github.com/JacksonZZS',
  }

  await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => null)

  const loginResponse = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: payload.username,
      password: payload.password,
    }),
  })

  if (!loginResponse.ok) {
    throw new Error(`Login failed: ${loginResponse.status} ${loginResponse.statusText}`)
  }

  return loginResponse.json()
}

async function waitForStablePage(page, ms = 2500) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(ms)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
        caret-color: transparent !important;
      }
    `,
  }).catch(() => null)
}

async function capture(page, route, filename) {
  await page.goto(`${FRONTEND_URL}${route}`, { waitUntil: 'domcontentloaded' })
  await waitForStablePage(page)
  await page.screenshot({
    path: path.join(outputDir, filename),
    fullPage: true,
  })
  console.log(`captured ${filename}`)
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true })

  const auth = await ensureDemoAuth()
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
    colorScheme: 'light',
  })

  await context.addInitScript((data) => {
    window.localStorage.setItem(
      'auth-storage',
      JSON.stringify({
        state: {
          user: data.user,
          token: data.access_token,
        },
        version: 0,
      })
    )
  }, auth)

  const page = await context.newPage()

  await capture(page, '/', 'dashboard-task-console.png')
  await capture(page, '/manual-review', 'manual-review-card.png')
  await capture(page, '/optimizer', 'resume-optimizer.png')
  await capture(page, '/resumes', 'resume-library.png')
  await capture(page, '/market-intelligence', 'market-intelligence.png')

  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
