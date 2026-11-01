import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
export const api = 'http://127.0.0.1:18000/api/v1'
export const password = 'Course-test-2026'
export async function submitLogin(page: Page, button = '登录合账', registering = false) {
  const endpoints = registering ? ['register', 'login', 'me'] : ['login', 'me']
  // Password hashing can take several seconds on shared Windows runners. Wait
  // for the actual authentication chain, then assert navigation separately.
  await Promise.all([
    ...endpoints.map(endpoint => page.waitForResponse(
      response => new URL(response.url()).pathname === `/api/v1/auth/${endpoint}`,
      { timeout: 30_000 },
    ).then(response => expect(response.status()).toBe(endpoint === 'register' ? 201 : 200))),
    page.getByRole('button', { name: button, exact: true }).click(),
  ])
}
export async function refreshActivity(page: Page) {
  const id = Number(page.url().split('/').at(-1))
  const refresh = page.getByRole('button', { name: '刷新', exact: true })
  const [results] = await Promise.all([
    Promise.all(['', '/members', '/statistics'].map(suffix => page.waitForResponse(
      response => new URL(response.url()).pathname === `/api/v1/activities/${id}${suffix}`
        && response.request().method() === 'GET',
      { timeout: 30_000 },
    ))),
    refresh.click(),
  ])
  for (const response of results) expect(response.ok()).toBeTruthy()
  // load() applies all three responses together. A resolved HTTP response alone
  // does not mean Vue has updated the members used to initialize expense forms.
  await expect(refresh).not.toHaveClass(/is-loading/)
}
export async function register(page: Page, name = '小王') {
  const account = `u_${randomUUID().replaceAll('-', '').slice(0,20)}`
  await page.goto('/register')
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('显示名', { exact: true }).fill(name)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await submitLogin(page, '创建账号并登录', true)
  await expect(page).toHaveURL(/\/activities$/)
  return account
}
export async function createActivity(page: Page, name: string) {
  await page.getByRole('button', { name: '创建活动', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '创建新活动' })
  await dialog.getByLabel('活动名称').fill(name)
  await dialog.getByLabel('总预算').fill('200')
  await dialog.getByRole('button', { name: '创建活动', exact: true }).click()
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
  return Number(page.url().split('/').at(-1))
}
export async function join(page: Page, code: string) {
  await page.getByRole('button', { name: '邀请码加入' }).click()
  await page.getByLabel('邀请码', { exact: true }).fill(code)
  await page.getByRole('button', { name: '加入活动', exact: true }).click()
  await expect(page).toHaveURL(/\/activities\/\d+$/)
}
export async function headers(request: APIRequestContext, account: string) {
  const response = await request.post(`${api}/auth/login`, { data: { username: account, password } })
  expect(response.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await response.json()).access_token}` }
}
export async function expenseForm(page: Page, title: string, amount: string) {
  await page.getByRole('button', { name: '费用明细', exact: true }).click()
  await page.getByRole('button', { name: '新增费用', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增费用' })
  await dialog.getByLabel('费用名称', { exact: true }).fill(title)
  await dialog.getByLabel('费用总额（元）').fill(amount)
  return dialog
}
