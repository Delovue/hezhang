import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { api, createActivity, headers, password, refreshActivity, register } from './helpers'

async function sharedActivity(page: Page, request: APIRequestContext) {
  const account = await register(page, '小王')
  const id = await createActivity(page, '协作刷新')
  await expect(page.locator('.own-card')).toContainText('你已平账')
  const ownerAuth = await headers(request, account)
  const guestAccount = `u_${randomUUID().replaceAll('-', '').slice(0, 20)}`
  const registration = await request.post(`${api}/auth/register`, {
    data: { username: guestAccount, display_name: '小李', password },
  })
  expect(registration.status()).toBe(201)
  const guestUser = await registration.json()
  const guestAuth = await headers(request, guestAccount)
  const joined = await request.post(`${api}/activities/join`, {
    headers: guestAuth, data: { invite_code: await page.getByTestId('invite-code').innerText() },
  })
  expect(joined.ok()).toBeTruthy()
  const response = await request.get(`${api}/activities/${id}/members`, { headers: ownerAuth })
  expect(response.ok()).toBeTruthy()
  const members: { id: number; user_id: number }[] = await response.json()
  const guestId = members.find(member => member.user_id === guestUser.id)!.id
  const ownerId = members.find(member => member.id !== guestId)!.id
  return { id, ownerId, guestId, ownerAuth, guestAuth, members }
}

async function addExpense(request: APIRequestContext, activity: Awaited<ReturnType<typeof sharedActivity>>, payer: number) {
  const response = await request.post(`${api}/activities/${activity.id}/expenses`, {
    headers: activity.guestAuth,
    data: { title: '伙伴新增餐费', category: '餐饮', amount_cents: 1000, expense_date: '2026-11-01',
      payer_member_id: payer, split_method: 'EQUAL', request_id: randomUUID(),
      participants: activity.members.map(member => ({ member_id: member.id })) },
  })
  expect(response.status()).toBe(201)
}

test('switching tabs refreshes members, totals, settlement summary and activity status together', async ({ page, request }) => {
  const activity = await sharedActivity(page, request)
  await page.getByRole('button', { name: /活动成员/ }).click()
  await expect(page.locator('.member-card')).toHaveCount(2)

  await addExpense(request, activity, activity.guestId)
  await page.getByRole('button', { name: '结算与付款', exact: true }).click()
  await expect(page.getByTestId('total-spent')).toHaveText('¥ 10.00')
  await expect(page.locator('.own-card')).toContainText('付给小李 ¥ 5.00')
  await expect(page.getByTestId(`balance-${activity.ownerId}`)).toContainText('应付 ¥ 5.00')

  const updated = await request.patch(`${api}/activities/${activity.id}`, {
    headers: activity.ownerAuth, data: { name: '协作刷新', budget_cents: 30000 },
  })
  expect(updated.ok()).toBeTruthy()
  await page.getByRole('button', { name: '活动概览', exact: true }).click()
  await expect(page.getByTestId('budget')).toContainText('预算 ¥ 300.00')
  await expect(page.locator('.member-share')).toHaveCount(2)

  const sealed = await request.post(`${api}/activities/${activity.id}/start-settlement`, { headers: activity.ownerAuth })
  expect(sealed.ok()).toBeTruthy()
  await page.getByRole('button', { name: '费用明细', exact: true }).click()
  await expect(page.locator('.detail-title')).toContainText('结算中')
  await expect(page.getByRole('button', { name: '新增费用', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '登记已付款', exact: true })).toBeVisible()
})

test('the pending receipt shortcut refreshes even when the settlement tab is already open', async ({ page, request }) => {
  const activity = await sharedActivity(page, request)
  await addExpense(request, activity, activity.ownerId)
  expect((await request.post(`${api}/activities/${activity.id}/start-settlement`, { headers: activity.ownerAuth })).ok()).toBeTruthy()
  const response = await request.post(`${api}/activities/${activity.id}/payments`, {
    headers: activity.guestAuth, data: { payee_member_id: activity.ownerId, amount_cents: 500, request_id: randomUUID() },
  })
  expect(response.status()).toBe(201)
  const payment = await response.json()
  await refreshActivity(page)
  await page.getByRole('button', { name: '去处理', exact: true }).click()
  await expect(page.getByTestId(`payment-${payment.id}`)).toContainText('待收款人确认')

  expect((await request.post(`${api}/activities/${activity.id}/payments/${payment.id}/cancel`, { headers: activity.guestAuth })).ok()).toBeTruthy()
  await page.getByRole('button', { name: '去处理', exact: true }).click()
  await expect(page.getByTestId(`payment-${payment.id}`)).toContainText('已撤销')
  await expect(page.getByRole('button', { name: '去处理', exact: true })).toHaveCount(0)
  await expect(page.locator('.own-card')).toContainText('还应收回 ¥ 5.00，来自小李')
})
