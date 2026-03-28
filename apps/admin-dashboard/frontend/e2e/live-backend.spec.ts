import { expect, test } from '@playwright/test'
import { loginAsRole, setStoredRole } from './helpers'

test('live backend login bootstrap resolves lecturer into portal overview', async ({ page }) => {
    await loginAsRole(page, 'lecturer')
    await expect(page).toHaveURL(/\/portal$/)
    await expect(page.getByRole('heading', { name: 'Portal overview', level: 1 })).toBeVisible()
})

test('live backend chat responds through the proxied /web BFF', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/chat')

    await expect(page.getByRole('heading', { name: 'Assistant chat' })).toBeVisible()
    await page.getByPlaceholder('Ask a question to validate chat states...').fill('Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?')
    await page.getByRole('button', { name: 'Send mock message' }).click()

    await expect(page.getByText('Day la phan hoi tu /web backend cho cau hoi').last()).toBeVisible()
    await page.getByRole('link', { name: /Quy dinh hoc vu 2024-2025/i }).first().click()
    await expect(page.getByRole('heading', { name: 'Document detail' })).toBeVisible()
})

test('live backend document actions update detail state and audit visibility', async ({ page }) => {
    await loginAsRole(page, 'admin')

    await page.goto('/documents/doc-004')

    await expect(page.getByRole('button', { name: 'Reindex document' })).toBeVisible()
    await page.getByRole('button', { name: 'Reindex document' }).click()
    await expect(page.getByText('Reindex started for Thong bao lich dang ky mon hoc')).toBeVisible()
    await expect(page.getByText('indexing', { exact: true })).toBeVisible()

    await page.getByRole('button', { name: 'Archive document' }).click()
    await expect(page.getByText('Archived Thong bao lich dang ky mon hoc')).toBeVisible()
    await expect(page.getByText('archived', { exact: true })).toBeVisible()

    await page.goto('/admin/audit-logs')
    await expect(page.getByRole('heading', { name: 'Audit logs', level: 1 })).toBeVisible()
    await page.getByPlaceholder('Search by actor, action or target...').fill('Thong bao lich dang ky mon hoc')
    await expect(page.locator('tbody').getByText('archive document').first()).toBeVisible()
    await expect(page.locator('tbody').getByText('reindex document').first()).toBeVisible()
})

test('live backend auth error remains distinct from access denied', async ({ page }) => {
    await page.goto('/portal/upload?scenario=auth-error')

    await expect(page.getByRole('heading', { name: 'Unable to validate session' })).toBeVisible()
    await expect(page.getByText('Unable to validate the current session.')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Switch role' })).toBeVisible()
})

test('live backend blocks non-compliant internal bootstrap before portal access', async ({ page }) => {
    await page.goto('/auth/callback?bootstrap=1&role=lecturer&scenario=non-compliant-internal-email')

    await expect(page.getByRole('heading', { name: 'Session callback' })).toBeVisible()
    await expect(page.getByText('The current session does not satisfy the institutional domain rule.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Retry bootstrap' })).toBeVisible()
})

test('live backend denies student access to protected portal routes after login', async ({ page }) => {
    await loginAsRole(page, 'student')
    await page.goto('/portal/upload')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
    await expect(page.getByText('Attempted route: /portal/upload')).toBeVisible()
})

test('live backend logout clears the session cookie and returns to login', async ({ page }) => {
    await loginAsRole(page, 'operator')
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()

    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/auth\/login$/)

    await page.goto('/portal/review')
    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
})
