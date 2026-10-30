import { expect, test } from '@playwright/test'
import { api, createActivity, expenseForm, headers, register } from './helpers'

test('history retains deleted expenses and renders before/after values with query filters', async ({ page }) => {
  await register(page, '小王'); await createActivity(page, '修改追溯')
  let dialog = await expenseForm(page, '原费用名称', '10')
  await dialog.getByRole('button', { name: '保存费用' }).click()
  await expect(dialog).not.toBeVisible()
  await page.getByRole('button', { name: '编辑费用', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '编辑费用' })
  await dialog.getByLabel('费用名称', { exact: true }).fill('修正后的费用')
  await dialog.getByLabel('费用总额（元）').fill('10.01')
  await dialog.getByRole('button', { name: '保存费用' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.locator('.expense-card')).toContainText('修正后的费用')
  await page.getByRole('button', { name: '删除费用', exact: true }).click()
  await page.getByRole('button', { name: '确认删除' }).click()
  await expect(page.locator('.expense-card')).toHaveCount(0)
  await page.getByRole('button', { name: '操作历史', exact: true }).click()
  await expect(page.locator('.audit-entry')).toHaveCount(4)
  const changed = page.locator('.audit-entry').filter({ hasText: '修改费用' })
  await changed.getByText('查看变更详情').click()
  await expect(changed.locator('[data-field="title"]')).toContainText('原费用名称')
  await expect(changed.locator('[data-field="title"]')).toContainText('修正后的费用')
  await expect(changed.locator('[data-field="amount_cents"]')).toContainText('¥ 10.00')
  await expect(changed.locator('[data-field="amount_cents"]')).toContainText('¥ 10.01')
  await page.getByLabel('操作类型', { exact: true }).selectOption('EXPENSE_DELETED')
  await page.getByRole('button', { name: '筛选历史' }).click()
  await expect(page.locator('.audit-entry')).toHaveCount(1)
  await expect(page.locator('.audit-entry')).toContainText('小王 · 删除费用')
  await page.getByLabel('对象编号', { exact: true }).fill('1')
  await page.getByRole('button', { name: '筛选历史' }).click()
  await expect(page.locator('.ledger-panel').getByRole('alert')).toContainText('选择对象类型')
})

test('cursor pagination remains stable when new audit entries arrive between pages', async ({ page, request }) => {
  const account = await register(page, '小王'); const id = await createActivity(page, '历史分页')
  const auth = await headers(request, account)
  const members = await (await request.get(`${api}/activities/${id}/members`, { headers: auth })).json()
  async function create(title: string) {
    const response = await request.post(`${api}/activities/${id}/expenses`, { headers: auth, data: {
      title, amount_cents: 1, category: '其他', expense_date: '2026-10-30', payer_member_id: members[0].id,
      split_method: 'EQUAL', participants: [{ member_id: members[0].id }],
    } })
    expect(response.status()).toBe(201)
  }
  for (let i = 0; i < 25; i++) await create(`历史 ${i}`)
  await page.getByRole('button', { name: '操作历史', exact: true }).click()
  await expect(page.locator('.audit-entry')).toHaveCount(20)
  const newest = Number(await page.locator('.audit-entry').first().getAttribute('data-audit-id'))
  await create('分页期间的新记录')
  await page.getByRole('button', { name: '加载更早历史' }).click()
  await expect(page.locator('.audit-entry')).toHaveCount(26)
  const ids = await page.locator('.audit-entry').evaluateAll(nodes => nodes.map(node => Number(node.getAttribute('data-audit-id'))))
  expect(new Set(ids).size).toBe(26)
  expect(Math.max(...ids)).toBe(newest)
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.locator('.audit-entry').first()).toHaveAttribute('data-audit-id', String(newest + 1))
})
