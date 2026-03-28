import { expect, test } from '@playwright/test'

test('login bootstrap resolves lecturer into the contributor portal', async ({ page }) => {
    await page.goto('/auth/login')

    await expect(page.getByRole('heading', { name: 'Session bootstrap' })).toBeVisible()
    await page.getByRole('button', { name: 'Continue as lecturer' }).click()

    await expect(page).toHaveURL(/\/portal$/)
    await expect(page.getByRole('heading', { name: 'Portal overview', level: 1 })).toBeVisible()
})

test('login bootstrap resolves admin into the admin shell', async ({ page }) => {
    await page.goto('/auth/login')

    await page.getByRole('button', { name: 'Continue as admin' }).click()

    await expect(page).toHaveURL(/\/admin\/users$/)
    await expect(page.getByRole('heading', { name: 'Users', level: 1 })).toBeVisible()
})
