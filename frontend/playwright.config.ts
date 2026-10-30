import { defineConfig, devices } from '@playwright/test'
import { resolve } from 'node:path'

process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(import.meta.dirname, '../.cache/ms-playwright')
const python = process.platform === 'win32'
  ? '../backend/.venv/Scripts/python.exe' : '../backend/.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:15173',
    locale: 'zh-CN',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    { command: `"${python}" ../scripts/frontend_e2e_server.py`, url: 'http://127.0.0.1:18000/health',
      reuseExistingServer: false, timeout: 30_000 },
    { command: 'npm run dev -- --port 15173', url: 'http://127.0.0.1:15173',
      env: { HEZHANG_API_TARGET: 'http://127.0.0.1:18000' }, reuseExistingServer: false, timeout: 30_000 },
  ],
})
