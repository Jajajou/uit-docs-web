import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('public chat can send a message and open a citation', async ({ page }) => {
    await setStoredRole(page, 'guest')
    await page.goto('/')

    await expect(page.getByRole('heading', { name: 'UIT Knowledge Portal' })).toBeVisible()
    await page.getByRole('link', { name: 'Open chat' }).click()

    await expect(page.getByRole('heading', { name: 'Assistant chat' })).toBeVisible()
    await page.getByLabel('Search conversations').fill('Lich dang ky')
    await page.getByPlaceholder('Ask a question to validate chat states...').fill('Lich dang ky mon hoc cho khoa 2024 bat dau khi nao?')
    await page.getByRole('button', { name: 'Send mock message' }).click()

    await expect(page.getByText('Day la phan hoi contract-backed cho cau hoi').last()).toBeVisible()
    await page.getByRole('link', { name: /Quy dinh hoc vu 2024-2025|Thong bao hoc phi hoc ky 2/i }).first().click()

    await expect(page.getByRole('heading', { name: 'Document detail' })).toBeVisible()
})
