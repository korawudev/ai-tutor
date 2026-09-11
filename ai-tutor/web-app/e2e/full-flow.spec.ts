import { test, expect, type Page } from '@playwright/test'

const TEST_EMAIL = `e2e-${Date.now()}@test.com`
const TEST_USER = `e2e-user-${Date.now()}`
const TEST_PASS = 'Test1234!'

async function register(page: Page) {
  await page.goto('/')
  await page.waitForURL('**/login')
  await page.getByText('没有账号？去注册').click()
  await page.getByLabel('邮箱').fill(TEST_EMAIL)
  await page.getByLabel('用户名').fill(TEST_USER)
  await page.getByLabel('密码').fill(TEST_PASS)
  await page.getByRole('button', { name: '注册' }).click()
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 10_000 })
}

async function login(page: Page) {
  await page.goto('/')
  await page.waitForTimeout(1000)
  // After register, the user is already authenticated and lands on dashboard
  if (await page.getByRole('heading', { name: '仪表盘' }).isVisible({ timeout: 3000 })) {
    return
  }
  await page.getByLabel('邮箱').fill(TEST_EMAIL)
  await page.getByLabel('密码').fill(TEST_PASS)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 10_000 })
}

test.describe('Full user flow', () => {
  test('1. register and login', async ({ page }) => {
    await register(page)
    await login(page)
    await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()
  })

  test('2. import document', async ({ page }) => {
    await login(page)
    await page.goto('/documents')
    await page.waitForTimeout(1000)

    await page.getByPlaceholder('输入 URL 导入...').fill('https://docs.python.org/3/tutorial/classes.html')
    await page.getByPlaceholder('标签（逗号分隔）').fill('python,oop')
    await page.getByRole('button', { name: '导入' }).click()

    await page.waitForResponse(
      (resp) => resp.url().includes('/api/documents/import') && resp.status() === 200,
      { timeout: 60_000 }
    )

    await page.waitForTimeout(2000)
    const docCards = page.locator('.font-medium.truncate')
    const count = await docCards.count()
    expect(count).toBeGreaterThan(0)
  })

  test('3. duplicate detection shows modal', async ({ page }) => {
    await login(page)
    await page.goto('/documents')
    await page.waitForTimeout(1000)

    await page.getByPlaceholder('输入 URL 导入...').fill('https://docs.python.org/3/tutorial/classes.html')
    await page.getByRole('button', { name: '导入' }).click()

    await page.waitForResponse(
      (resp) => resp.url().includes('/api/documents/import') && resp.status() === 200,
      { timeout: 60_000 }
    )

    const modal = page.getByText('检测到重复文档')
    await expect(modal).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: '放弃导入' }).click()
    await expect(modal).not.toBeVisible()
  })

  test('4. re-import overwrites old document', async ({ page }) => {
    await login(page)
    await page.goto('/documents')
    await page.waitForTimeout(1000)

    await page.getByPlaceholder('输入 URL 导入...').fill('https://docs.python.org/3/tutorial/classes.html')
    await page.getByRole('button', { name: '导入' }).click()

    await page.waitForResponse(
      (resp) => resp.url().includes('/api/documents/import') && resp.status() === 200,
      { timeout: 60_000 }
    )

    await page.getByText('检测到重复文档').waitFor({ timeout: 10_000 })
    await page.getByRole('button', { name: '重新导入' }).click()

    await page.waitForResponse(
      (resp) => resp.url().includes('/api/documents/import') && resp.status() === 200,
      { timeout: 60_000 }
    )

    await page.waitForTimeout(2000)
    const modal = page.getByText('检测到重复文档')
    await expect(modal).not.toBeVisible()
  })

  test('5. delete document', async ({ page }) => {
    await login(page)
    await page.goto('/documents')
    await page.waitForTimeout(2000)

    const deleteBtn = page.locator('button').filter({ has: page.locator('svg') }).last()
    page.on('dialog', (dialog) => dialog.accept())
    await deleteBtn.click()

    await page.waitForTimeout(1000)
  })

  test('6. navigate to quiz page', async ({ page }) => {
    await login(page)
    await page.goto('/quiz')
    await page.waitForTimeout(1000)
    await expect(page.locator('body')).toContainText('练习')
  })

  test('7. navigate to review page', async ({ page }) => {
    await login(page)
    await page.goto('/review')
    await page.waitForTimeout(1000)
    await expect(page.locator('body')).toContainText('复习')
  })

  test('8. navigate to feynman page', async ({ page }) => {
    await login(page)
    await page.goto('/feynman')
    await page.waitForTimeout(1000)
    await expect(page.locator('body')).toContainText('费曼')
  })

  test('9. dashboard shows stats', async ({ page }) => {
    await login(page)
    await page.goto('/')
    await page.waitForTimeout(2000)
    await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()
  })
})
