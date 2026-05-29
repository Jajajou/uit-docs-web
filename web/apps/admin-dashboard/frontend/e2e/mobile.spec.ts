import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { loginAsRole, setStoredRole } from './helpers'

test.use({
    viewport: { width: 390, height: 844 },
})

async function expectNoBlockingHorizontalOverflow(page: Page) {
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasOverflow).toBe(false)
}

test('mobile chat stays usable and free of blocking overflow', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/chat')

    await expect(page.getByRole('heading', { name: 'UIT AI' })).toBeVisible()
    await expect(page.getByLabel('Hỏi UIT AI')).toBeVisible()
    await page.getByLabel('Lịch sử').click()
    await expect(page.locator('aside').first()).toBeVisible()
    await expectNoBlockingHorizontalOverflow(page)
})

test('mobile admin manager keeps search and filters reachable', async ({ page }) => {
    await loginAsRole(page, 'admin', '/manager')

    await expect(page.getByPlaceholder(/Tìm theo tên hoặc email/i)).toBeVisible()
    await expect(page.getByLabel(/^Lọc người dùng theo vai trò$/i)).toBeVisible()
    await expect(page.getByLabel(/^Lọc người dùng theo trạng thái$/i)).toBeVisible()
    await expect(page.getByLabel(/^Lọc người dùng theo trạng thái email$/i)).toBeVisible()
    await expectNoBlockingHorizontalOverflow(page)
})
