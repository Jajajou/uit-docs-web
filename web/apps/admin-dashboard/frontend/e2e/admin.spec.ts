import { expect, test } from '@playwright/test'
import { loginAsRole, setStoredRole } from './helpers'

test('student is blocked from manager routes', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/manager')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
})

test('admin can search, filter and review users from the manager shell', async ({ page }) => {
    await loginAsRole(page, 'admin', '/manager')

    await page.getByPlaceholder(/Tìm theo tên hoặc email/i).fill('admin@gm.uit.edu.vn')
    await expect(page.getByText(/admin@gm.uit.edu.vn/i)).toBeVisible()

    await page.getByLabel(/^Lọc người dùng theo vai trò$/i).click()
    await page.locator('[role="listbox"]').first().getByRole('option', { name: /Quản trị viên/i }).click()

    await expect(page.getByText(/Tran Van Admin/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /Lưu/i }).first()).toBeVisible()
})
