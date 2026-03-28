import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('guest is blocked from admin routes', async ({ page }) => {
    await setStoredRole(page, 'guest')
    await page.goto('/admin/users')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
})

test('admin can search the users page and access the admin shell', async ({ page }) => {
    await setStoredRole(page, 'admin')
    await page.goto('/admin/users')

    await expect(page.getByRole('heading', { name: 'Users', level: 1 })).toBeVisible()
    await page.getByPlaceholder('Search by name or email...').fill('Invite Pending Lecturer')
    await expect(page.getByText('Invite Pending Lecturer')).toBeVisible()
    await page.goto('/admin/audit-logs?scenario=dense-audit-history')
    await expect(page.getByRole('heading', { name: 'Audit logs', level: 1 })).toBeVisible()
})
