import { expect, test } from '@playwright/test'
import { loginAsRole } from './helpers'

test('login page keeps Google-only auth visible', async ({ page }) => {
    await page.goto('/auth/login')

    await expect(page.getByRole('button', { name: /Tiếp tục với Google/i })).toBeVisible()
    await expect(page.getByText(/Chỉ chấp nhận tài khoản Google chính thức được cấp bởi trường UIT/i)).toBeVisible()
})

test('mock bootstrap routes teacher and admin into the correct workspace', async ({ page }) => {
    await loginAsRole(page, 'teacher', '/upload')
    await expect(page.getByLabel(/Tiêu đề tài liệu/i)).toBeVisible()

    await loginAsRole(page, 'admin', '/manager')
    await expect(page.getByPlaceholder(/Tìm theo tên hoặc email/i)).toBeVisible()
})
