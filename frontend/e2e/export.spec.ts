import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { createActivity, expenseForm, register } from './helpers'

test('a member downloads a real CSV with Chinese text and safe spreadsheet cells', async ({ page }) => {
  await register(page, '小王'); await createActivity(page, '导出验证')
  const dialog = await expenseForm(page, '=中文,1+1', '1.01')
  await dialog.getByRole('button', { name: '保存费用' }).click()
  await expect(dialog).not.toBeVisible()
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出费用 CSV' }).click()
  const download = await downloading
  expect(download.suggestedFilename()).toBe('导出验证-费用明细.csv')
  const data = await readFile((await download.path())!)
  expect([...data.subarray(0,3)]).toEqual([0xef, 0xbb, 0xbf])
  expect(data.toString('utf8')).toContain('"\'=中文,1+1"')
  expect(data.toString('utf8')).toContain('1.01')
})
