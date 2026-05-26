import { expect, test } from '@playwright/test'
import { loginAsLiveRole, resetLiveBackendState, setStoredRole } from './helpers'

test.beforeEach(async ({ page }) => {
    await resetLiveBackendState(page.request)
})

test('live backend bootstrap resolves teacher into upload workspace', async ({ page }) => {
    await loginAsLiveRole(page, 'teacher')
    await expect(page).toHaveURL(/\/upload$/)
    await expect(page.getByRole('heading', { name: /Nạp tài liệu vào luồng duyệt nội bộ/i })).toBeVisible()
})

test('live backend chat responds through the proxied /web BFF', async ({ page }) => {
    await loginAsLiveRole(page, 'student')

    await expect(page.getByRole('heading', { name: 'UIT AI' })).toBeVisible()
    await page.getByLabel('Hỏi UIT AI').fill('Lịch đăng ký môn học của khóa 2024 bắt đầu khi nào?')
    await page.getByRole('button', { name: /Gửi/i }).click()

    const sourceButton = page.getByRole('button', { name: /Nguồn tài liệu/i }).last()
    await expect(sourceButton).toBeVisible()
    await sourceButton.click()
    await expect(page.getByText(/Nguồn đang được trích dẫn/i)).toBeVisible()
    await expect(page.getByText(/Thong bao lich dang ky mon hoc|Quy dinh hoc vu 2024-2025/i).first()).toBeVisible()
    await page.locator('aside a').first().click()
    await expect(page.getByRole('heading', { name: /Chi tiết tài liệu/i })).toBeVisible()
})

test('live backend document actions update detail state for admin workflows', async ({ page }) => {
    await loginAsLiveRole(page, 'admin')

    await page.goto('/documents/doc-004')

    await expect(page.getByRole('button', { name: /Lập chỉ mục lại/i })).toBeVisible()
    await page.getByRole('button', { name: /Lập chỉ mục lại/i }).click()
    await expect(page.getByText(/xếp hàng lập chỉ mục lại/i)).toBeVisible()

    await page.goto('/manager')
    await expect(page.getByRole('heading', { name: /Phân quyền người dùng và kiểm soát nội bộ/i })).toBeVisible()
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

    await expect(page.getByRole('heading', { name: /Không thể xác thực phiên làm việc/i })).toBeVisible()
    await expect(page.getByText(/does not satisfy the institutional domain rule/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /Thử bootstrap lại/i })).toBeVisible()
})

test('live backend denies student access to protected portal routes after login', async ({ page }) => {
    await loginAsLiveRole(page, 'student')
    await page.goto('/upload')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
    await expect(page.getByText('Attempted route: /upload')).toBeVisible()
})

test('live backend logout clears the session cookie and blocks protected routes', async ({ page }) => {
    await loginAsLiveRole(page, 'admin')
    await expect(page.getByRole('button', { name: /Đăng xuất/i })).toBeVisible()

    await page.getByRole('button', { name: /Đăng xuất/i }).click()
    await expect(page).toHaveURL(/\/(auth\/login|403)$/)

    await page.goto('/manager')
    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
})
