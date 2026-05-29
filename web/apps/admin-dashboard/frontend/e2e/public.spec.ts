import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('student chat can send a message and open a cited document', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/chat')

    await expect(page.getByRole('heading', { name: 'UIT AI' })).toBeVisible()
    await page.getByRole('button', { name: /học phí học kỳ này/i }).click()
    await expect(page.getByLabel('Hỏi UIT AI')).toHaveValue(/học phí/i)
    await page.getByRole('button', { name: /gửi/i }).click()

    await expect(page.getByText(/UIT AI/i).nth(1)).toBeVisible()
    await expect(page.getByRole('button', { name: /Nguồn tài liệu/i }).last()).toBeVisible()
    await page.getByRole('button', { name: /Nguồn tài liệu/i }).last().click()
    await expect(page.getByText(/Nguồn đang được trích dẫn/i)).toBeVisible()
    await page.locator('aside a').first().click()

    await expect(page).toHaveURL(/\/documents\//)
    await expect(page.getByRole('heading', { name: /Chi tiết tài liệu/i })).toBeVisible()
})
