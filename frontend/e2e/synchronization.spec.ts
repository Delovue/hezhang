import { expect, test } from '@playwright/test'
import { createActivity, expenseForm, join, refreshActivity, register } from './helpers'

test('registration waits for the real authentication chain beyond the UI assertion deadline', async ({ page }) => {
  // Delay a successful real login response beyond Playwright's 5s UI assertion
  // deadline. This is controlled latency injection, not a sleep to hide a race.
  await page.route('**/api/v1/auth/login', async route => {
    const response = await route.fetch()
    await new Promise(resolve => setTimeout(resolve, 5_500))
    await route.fulfill({ response })
  })
  await register(page, '慢速认证')
  await expect(page).toHaveURL(/\/activities$/)
  await expect(page.getByRole('button', { name: '创建活动', exact: true })).toBeVisible()
})

test('a delayed member refresh finishes before a new expense captures its participants', async ({ page, browser }) => {
  await register(page, '小王')
  const id = await createActivity(page, '延迟成员刷新')
  const code = await page.getByTestId('invite-code').innerText()
  const context = await browser.newContext()
  try {
    const guest = await context.newPage()
    await register(guest, '小李'); await join(guest, code)
    await page.route(`**/api/v1/activities/${id}/members`, async route => {
      const response = await route.fetch()
      await new Promise(resolve => setTimeout(resolve, 1_000))
      await route.fulfill({ response })
    })
    await refreshActivity(page)
    const dialog = await expenseForm(page, '两人均摊', '1.01')
    await expect(dialog.getByLabel('参与分摊：小李', { exact: true })).toBeChecked()
    await dialog.getByRole('button', { name: '预览分摊' }).click()
    await expect(dialog.locator('.preview-box')).toContainText('小王：¥ 0.51')
    await expect(dialog.locator('.preview-box')).toContainText('小李：¥ 0.50')
  } finally { await context.close() }
})
