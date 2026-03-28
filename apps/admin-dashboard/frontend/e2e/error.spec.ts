import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('auth error state is distinct from access denied', async ({ page }) => {
    await setStoredRole(page, 'lecturer')
    await page.goto('/portal/upload?scenario=auth-error')

    await expect(page.getByRole('heading', { name: 'Unable to validate session' })).toBeVisible()
    await expect(page.getByText('Unable to validate the current session.')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Switch role' })).toBeVisible()
})

test('chat error state remains stable without crashing the shell', async ({ page }) => {
    await setStoredRole(page, 'guest')
    await page.goto('/chat?scenario=error')

    await expect(page.getByRole('heading', { name: 'Assistant chat' })).toBeVisible()
    await page.getByPlaceholder('Ask a question to validate chat states...').fill('Hoc phi hien tai la bao nhieu?')
    await page.getByRole('button', { name: 'Send mock message' }).click()

    await expect(page.getByText('Unable to generate assistant response.')).toBeVisible()
})

test('admin error scenario stays readable and contained', async ({ page }) => {
    await setStoredRole(page, 'admin')
    await page.goto('/admin/users?scenario=error')

    await expect(page.getByRole('heading', { name: 'Users', level: 1 })).toBeVisible()
    await expect(page.getByText('Unable to load admin users.')).toBeVisible()
})
