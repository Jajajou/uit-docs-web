import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test.use({
    viewport: { width: 390, height: 844 },
})

async function expectNoBlockingHorizontalOverflow(page: Page) {
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasOverflow).toBe(false)
}

test('mobile chat stays usable and free of blocking overflow', async ({ page }) => {
    await setStoredRole(page, 'guest')
    await page.goto('/chat')

    await expect(page.getByRole('heading', { name: 'Assistant chat' })).toBeVisible()
    await page.getByPlaceholder('Ask a question to validate chat states...').fill('Lich dang ky mon hoc cua khoa 2024 la khi nao?')
    await expect(page.getByRole('button', { name: 'Send mock message' })).toBeVisible()
    await expectNoBlockingHorizontalOverflow(page)
})

test('mobile operator library keeps search and filters reachable', async ({ page }) => {
    await setStoredRole(page, 'operator')
    await page.goto('/portal/library')

    await expect(page.getByRole('heading', { name: 'Knowledge library', level: 1 })).toBeVisible()
    await expect(page.getByLabel('Search')).toBeVisible()
    await expect(page.getByLabel('Filter by lifecycle')).toBeVisible()
    await expect(page.getByLabel('Filter by visibility')).toBeVisible()
    await expectNoBlockingHorizontalOverflow(page)
})
