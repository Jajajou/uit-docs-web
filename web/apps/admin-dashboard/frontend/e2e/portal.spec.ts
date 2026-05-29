import { expect, test } from '@playwright/test'
import { loginAsRole, setStoredRole } from './helpers'

test('teacher can submit a text upload draft', async ({ page }) => {
    await loginAsRole(page, 'teacher', '/upload')

    await page.getByRole('tab', { name: /Văn bản/i }).click()
    await page.getByRole('textbox', { name: /^Tiêu đề tài liệu$/i }).fill('Thông báo học phí hệ đào tạo chất lượng cao')
    await page.getByRole('textbox', { name: /^Đơn vị ban hành$/i }).fill('Phòng Đào tạo Đại học')
    await page
        .getByRole('textbox', { name: /^Nội dung văn bản$/i })
        .fill('Thông báo học phí hệ đào tạo chất lượng cao có hiệu lực từ học kỳ hè năm 2026 và đã đủ thông tin để hệ thống trích xuất.')
    await page.getByRole('checkbox', { name: /Đây là nguồn chính thức/i }).check()
    await page.getByRole('checkbox', { name: /Tài liệu đã sẵn sàng để admin rà soát/i }).check()
    await page.getByRole('button', { name: /Gửi tài liệu/i }).click()

    await expect(page.getByText(/Đã tạo phiếu nộp/i).first()).toBeVisible()
    await expect(page.getByText(/Thông báo học phí hệ đào tạo chất lượng cao/i)).toBeVisible()
})

test('teacher cannot access manager shell', async ({ page }) => {
    await setStoredRole(page, 'teacher')
    await page.goto('/manager')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
    await expect(page.getByText(/Attempted route: \/manager/i)).toBeVisible()
})
