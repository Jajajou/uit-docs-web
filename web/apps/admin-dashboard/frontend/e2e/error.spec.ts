import { expect, test } from '@playwright/test'
import { loginAsRole, setStoredRole } from './helpers'

test('auth error state is distinct from access denied', async ({ page }) => {
    await setStoredRole(page, 'teacher')
    await page.goto('/upload?scenario=auth-error')

    await expect(page.getByRole('heading', { name: 'Unable to validate session' })).toBeVisible()
    await expect(page.getByText(/Unable to validate the current session/i)).toBeVisible()
    await expect(page.getByRole('link', { name: 'Switch role' })).toBeVisible()
})

test('chat error state remains stable without crashing the shell', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/chat?scenario=error')

    await expect(page.getByRole('heading', { name: 'UIT AI' })).toBeVisible()
    await page.getByLabel('Hỏi UIT AI').fill('Học phí hiện tại là bao nhiêu?')
    await page.getByRole('button', { name: /Gửi/i }).click()

    await expect(page.getByText(/Unable to generate assistant response/i)).toBeVisible()
})

test('admin error scenario stays readable and contained', async ({ page }) => {
    await loginAsRole(page, 'admin', '/manager')
    await page.goto('/manager?scenario=error')

    await expect(page.getByText(/Unable to load admin users/i)).toBeVisible()
})
