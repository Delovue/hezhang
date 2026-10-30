import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'

const require = createRequire(import.meta.url)
const cli = resolve(dirname(require.resolve('playwright/package.json')), 'cli.js')
const result = spawnSync(process.execPath, [cli, 'install', 'chromium', ...process.argv.slice(2)], {
  stdio: 'inherit',
  windowsHide: true,
  env: {
    ...process.env,
    PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || resolve(import.meta.dirname, '../../.cache/ms-playwright'),
  },
})
if (result.error) console.error(result.error.message)
process.exit(result.status ?? 1)
