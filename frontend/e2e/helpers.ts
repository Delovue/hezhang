import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
export const api = 'http://127.0.0.1:18000/api/v1'
export const password = 'Course-test-2026'
export async function register(page: Page, name: string) {
  const account = `u_${randomUUID().replaceAll('-', '').slice(0,20)}`
  await page.goto('/register')
  await page.getByLabel('用户名', { exact: true }).fill(account)
  await page.getByLabel('显示名', { exact: true }).fill(name)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '创建账号并登录' }).click()
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
