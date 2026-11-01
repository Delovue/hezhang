import { expect, test, type Page, type APIRequestContext } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { register, submitLogin } from './helpers'

const password = 'Course-test-2026'
const api = 'http://127.0.0.1:18000/api/v1'
function username() { return `u_${randomUUID().replaceAll('-', '').slice(0, 20)}` }
async function createActivity(page: Page, name: string, budget = '') {
  await page.getByRole('button', { name: '创建活动', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '创建新活动' })
  await dialog.getByLabel('活动名称').fill(name)
  if (budget) await dialog.getByLabel('总预算').fill(budget)
  await dialog.getByRole('button', { name: '创建活动', exact: true }).click()
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
}
async function apiAccount(request: APIRequestContext) {
  const account = username()
  const registration = await request.post(`${api}/auth/register`, { data: { username: account, display_name: '测试伙伴', password } })
  expect(registration.status()).toBe(201)
  const response = await request.post(`${api}/auth/login`, { data: { username: account, password } })
  const body = await response.json()
  return { account, headers: { Authorization: `Bearer ${body.access_token}` } }
}
async function login(page: Page, account: string) {
  await page.goto('/login')
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await submitLogin(page)
  await expect(page).toHaveURL(/\/activities$/)
}

test('two independent accounts create, join and see the real members and owner permissions', async ({ page, browser, request }) => {
  const account = await register(page, '小王')
  await createActivity(page, '周末杭州之旅', '0')
  await expect(page.locator('.metric-card').nth(1).getByText('¥ 0.00', { exact: true })).toBeVisible()
  const code = await page.getByTestId('invite-code').innerText()
  const id = page.url().split('/').at(-1)
  const other = await browser.newContext()
  try {
    const guest = await other.newPage()
    await register(guest, '小李')
    await guest.getByRole('button', { name: '邀请码加入' }).click()
    await guest.getByLabel('邀请码', { exact: true }).fill(code)
    await guest.getByRole('button', { name: '加入活动', exact: true }).click()
    await expect(guest).toHaveURL(new RegExp(`/activities/${id}$`))
    await expect(guest.getByRole('button', { name: '编辑活动' })).toHaveCount(0)
    await expect(guest.getByTestId('invite-code')).toHaveCount(0)
    await guest.getByRole('button', { name: /活动成员/ }).click()
    await expect(guest.locator('.member-card')).toHaveCount(2)
    await expect(guest.getByText('小王', { exact: true })).toBeVisible()
    await expect(guest.getByText('小李 （我）', { exact: true })).toBeVisible()
    const tokenResponse = await request.post(`${api}/auth/login`, { data: { username: account, password } })
    const token = await tokenResponse.json()
    const headers = { Authorization: `Bearer ${token.access_token}` }
    const memberResponse = await request.get(`${api}/activities/${id}/members`, { headers })
    const memberRows: { id: number }[] = await memberResponse.json()
    const expense = await request.post(`${api}/activities/${id}/expenses`, { headers, data: {
      title: '旅行午餐', category: '餐饮', amount_cents: 12000, expense_date: '2026-10-28',
      payer_member_id: memberRows[0]!.id, split_method: 'EQUAL',
      participants: memberRows.map((member) => ({ member_id: member.id })),
    } })
    expect(expense.status()).toBe(201)
    await page.getByRole('button', { name: '刷新', exact: true }).click()
    await expect(page.getByTestId('total-spent')).toHaveText('¥ 120.00')
    await expect(page.getByText('已超出预算', { exact: true })).toBeVisible()
    await expect(page.locator('.category-item').filter({ hasText: '餐饮' })).toContainText('¥ 120.00')
    await expect(page.locator('.member-share')).toHaveCount(2)
    await expect(page.locator('.member-share').filter({ hasText: '小李' })).toContainText('¥ 60.00')
    await page.screenshot({ path: 'test-results/activity-overview.png', fullPage: true })
    await page.getByRole('button', { name: /活动成员/ }).click()
    await expect(page.locator('.member-card')).toHaveCount(2)
    // Repeating a join must not duplicate membership.
    await guest.getByRole('link', { name: '返回我的活动' }).click()
    await guest.getByRole('button', { name: '邀请码加入' }).click()
    await guest.getByLabel('邀请码', { exact: true }).fill(code)
    await guest.getByRole('button', { name: '加入活动', exact: true }).click()
    await guest.getByRole('button', { name: /活动成员/ }).click()
    await expect(guest.locator('.member-card')).toHaveCount(2)
  } finally { await other.close() }
})

test('an owner edits a decimal budget and then clears it; refresh reauthenticates without losing saved data', async ({ page }) => {
  const account = await register(page)
  await createActivity(page, '周末聚餐')
  await page.getByRole('button', { name: '编辑活动' }).click()
  let dialog = page.getByRole('dialog', { name: '编辑活动' })
  await dialog.getByLabel('总预算').fill('1.01')
  await dialog.getByRole('button', { name: '保存修改' }).click()
  await expect(page.getByText('¥ 1.01', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '编辑活动' }).click()
  dialog = page.getByRole('dialog', { name: '编辑活动' })
  await dialog.getByLabel('总预算').fill('')
  await dialog.getByRole('button', { name: '保存修改' }).click()
  await expect(page.locator('.metric-card').nth(1).getByText('未设置', { exact: true })).toBeVisible()
  const detailUrl = page.url()
  await page.reload()
  await expect(page).toHaveURL(/\/login\?redirect=/)
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await submitLogin(page)
  await expect(page).toHaveURL(detailUrl)
  await expect(page.getByRole('heading', { name: '周末聚餐' })).toBeVisible()
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 })
})

test('a 401 preserves the editing draft and can resume with the same account', async ({ page }) => {
  await register(page)
  await createActivity(page, '保留原活动')
  await page.getByRole('button', { name: '编辑活动' }).click()
  const dialog = page.getByRole('dialog', { name: '编辑活动', exact: true })
  await dialog.getByLabel('活动名称').fill('登录后继续保存的草稿')
  await page.route('**/api/v1/activities/*', async (route) => {
    if (route.request().method() === 'PATCH') {
      await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: '请重新登录', code: 'AUTHENTICATION_REQUIRED', retryable: false }) })
    } else await route.continue()
  })
  await dialog.getByRole('button', { name: '保存修改' }).click()
  const resume = page.getByRole('dialog', { name: '重新登录，继续当前操作' })
  await expect(resume).toBeVisible()
  await resume.getByLabel('密码', { exact: true }).fill(password)
  await submitLogin(page, '重新登录')
  await expect(resume).not.toBeVisible()
  await expect(dialog.getByLabel('活动名称')).toHaveValue('登录后继续保存的草稿')
  await page.unroute('**/api/v1/activities/*')
  await dialog.getByRole('button', { name: '保存修改' }).click()
  await expect(page.getByRole('heading', { name: '登录后继续保存的草稿' })).toBeVisible()
})

test('filters, cursor pagination and a mobile layout use persisted activity data', async ({ page, request }) => {
  const actor = await apiAccount(request)
  for (let index = 0; index < 13; index++) {
    const response = await request.post(`${api}/activities`, { headers: actor.headers, data: { name: `分页活动 ${index}`, budget_cents: null } })
    expect(response.status()).toBe(201)
  }
  await login(page, actor.account)
  await expect(page.locator('a.activity-card')).toHaveCount(12)
  await page.getByRole('button', { name: '加载更多活动' }).click()
  await expect(page.locator('a.activity-card')).toHaveCount(13)
  await page.getByLabel('搜索活动名称').fill('分页活动 12')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.locator('a.activity-card')).toHaveCount(1)
  await page.getByRole('button', { name: '已归档', exact: true }).click()
  await expect(page.getByRole('heading', { name: '没有找到匹配的活动' })).toBeVisible()
  await page.getByRole('button', { name: '查看全部活动' }).click()
  await expect(page.locator('a.activity-card')).toHaveCount(12)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/activities-desktop.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: '创建活动', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/activities-mobile.png' })
})

test('invalid invites and wrong passwords show errors without navigation or losing inputs', async ({ page }) => {
  const account = await register(page)
  await page.getByRole('button', { name: '邀请码加入' }).click()
  await page.getByLabel('邀请码', { exact: true }).fill('does-not-exist')
  await page.getByRole('button', { name: '加入活动', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: '邀请码无效' })).toBeVisible()
  await expect(page.getByLabel('邀请码', { exact: true })).toHaveValue('does-not-exist')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill('wrong-password')
  const failedLogin = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/auth/login')
  await page.getByRole('button', { name: '登录合账', exact: true }).click()
  expect((await failedLogin).status()).toBe(401)
  await expect(page.getByRole('alert').filter({ hasText: '用户名或密码错误' })).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByLabel('用户名', { exact: true })).toHaveValue(account)
})

test('an uncertain activity creation blocks another POST until the user checks the list', async ({ page }) => {
  await register(page)
  await page.getByRole('button', { name: '创建活动', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '创建新活动' })
  await dialog.getByLabel('活动名称').fill('网络中断的活动')
  let posts = 0
  await page.route('**/api/v1/activities', async (route) => {
    if (route.request().method() === 'POST') {
      posts++
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '服务未就绪', code: 'DATABASE_NOT_READY', retryable: false }) })
    } else await route.continue()
  })
  await dialog.getByRole('button', { name: '创建活动', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '创建活动', exact: true })).toBeDisabled()
  await expect(dialog.getByLabel('活动名称')).toHaveValue('网络中断的活动')
  expect(posts).toBe(1)
  await dialog.getByRole('button', { name: '关闭并核对活动列表' }).click()
  await expect(dialog).not.toBeVisible()
})

test('non-members and invalid activity ids never expose another activity', async ({ page, request }) => {
  const actor = await apiAccount(request)
  const created = await request.post(`${api}/activities`, { headers: actor.headers, data: { name: '不可访问的活动' } })
  const activity = await created.json()
  const account = await register(page)
  // Refresh deliberately requires login; the saved redirect should return to a protected 404.
  await page.goto(`/activities/${activity.id}`)
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await submitLogin(page)
  await expect(page.getByRole('heading', { name: '活动不存在', exact: true })).toBeVisible()
  await expect(page.getByText('不可访问的活动', { exact: true })).toHaveCount(0)
  await page.getByRole('link', { name: '返回活动列表' }).click()
  await page.evaluate(() => { history.pushState({}, '', '/activities/9007199254740992'); dispatchEvent(new PopStateEvent('popstate')) })
  await expect(page.getByRole('heading', { name: '活动地址无效' })).toBeVisible()
})
