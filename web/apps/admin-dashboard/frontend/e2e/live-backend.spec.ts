import { expect, test } from '@playwright/test'
import { loginAsLiveRole, resetLiveBackendState, setStoredRole } from './helpers'

test.beforeEach(async ({ page }) => {
    await resetLiveBackendState(page.request)
})

test('live backend bootstrap resolves teacher into upload workspace', async ({ page }) => {
    await loginAsLiveRole(page, 'teacher')
    await expect(page).toHaveURL(/\/upload$/)
    await expect(page.getByRole('heading', { name: /Náº¡p tÃ i liá»‡u vÃ o luá»“ng duyá»‡t ná»™i bá»™/i })).toBeVisible()
})

test('live backend chat responds through the proxied /web BFF', async ({ page }) => {
    await loginAsLiveRole(page, 'student')

    await expect(page.getByRole('heading', { name: 'UIT AI' })).toBeVisible()
    await page.getByLabel('Há»i UIT AI').fill('Lá»‹ch Ä‘Äƒng kÃ½ mÃ´n há»c cá»§a khÃ³a 2024 báº¯t Ä‘áº§u khi nÃ o?')
    await page.getByRole('button', { name: /Gá»­i/i }).click()

    const sourceButton = page.getByRole('button', { name: /Nguá»“n tÃ i liá»‡u/i }).last()
    await expect(sourceButton).toBeVisible()
    await sourceButton.click()
    await expect(page.getByText(/Nguá»“n Ä‘ang Ä‘Æ°á»£c trÃ­ch dáº«n/i)).toBeVisible()
    await expect(page.getByText(/Thong bao lich dang ky mon hoc|Quy dinh hoc vu 2024-2025/i).first()).toBeVisible()
    await page.locator('aside a').first().click()
    await expect(page.getByRole('heading', { name: /Chi tiáº¿t tÃ i liá»‡u/i })).toBeVisible()
})

test('live backend document actions update detail state for admin workflows', async ({ page }) => {
    await loginAsLiveRole(page, 'admin')

    await page.goto('/documents/doc-004')

    await expect(page.getByRole('button', { name: /Láº­p chá»‰ má»¥c láº¡i/i })).toBeVisible()
    await page.getByRole('button', { name: /Láº­p chá»‰ má»¥c láº¡i/i }).click()
    await expect(page.getByText(/xáº¿p hÃ ng láº­p chá»‰ má»¥c láº¡i/i)).toBeVisible()

    await page.goto('/manager')
    await expect(page.getByRole('heading', { name: /PhÃ¢n quyá»n ngÆ°á»i dÃ¹ng vÃ  kiá»ƒm soÃ¡t ná»™i bá»™/i })).toBeVisible()
})

test('live backend auth error remains distinct from access denied', async ({ page }) => {
    await setStoredRole(page, 'teacher')
    await page.goto('/upload?scenario=auth-error')

    await expect(page.getByRole('heading', { name: 'Unable to validate session' })).toBeVisible()
    await expect(page.getByText(/Unable to validate the current session/i)).toBeVisible()
    await expect(page.getByRole('link', { name: 'Switch role' })).toBeVisible()
})

test('live backend blocks non-compliant internal bootstrap before portal access', async ({ page }) => {
    await page.goto('/auth/callback?bootstrap=1&role=teacher&scenario=non-compliant-internal-email')

    await expect(page.getByRole('heading', { name: /KhÃ´ng thá»ƒ xÃ¡c thá»±c phiÃªn lÃ m viá»‡c/i })).toBeVisible()
    await expect(page.getByText(/does not satisfy the institutional domain rule/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /Thá»­ bootstrap láº¡i/i })).toBeVisible()
})

test('live backend denies student access to protected portal routes after login', async ({ page }) => {
    await loginAsLiveRole(page, 'student')
    await page.goto('/upload')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
    await expect(page.getByText('Attempted route: /upload')).toBeVisible()
})

test('live backend logout clears the session cookie and blocks protected routes', async ({ page }) => {
    await loginAsLiveRole(page, 'admin')
    await expect(page.getByRole('button', { name: /ÄÄƒng xuáº¥t/i })).toBeVisible()

    await page.getByRole('button', { name: /ÄÄƒng xuáº¥t/i }).click()
    await expect(page).toHaveURL(/\/(auth\/login|403)$/)

    await page.goto('/manager')
    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
})
