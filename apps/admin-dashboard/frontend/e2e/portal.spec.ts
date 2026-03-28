import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('lecturer can submit a text upload draft', async ({ page }) => {
    await setStoredRole(page, 'lecturer')
    await page.goto('/portal/upload')

    await expect(page.getByRole('heading', { name: 'Upload workspace' })).toBeVisible()
    await page.getByRole('tab', { name: 'Text' }).click()
    await page.getByLabel('Submission title').fill('Thong bao hoc phi he dao tao chat luong cao')
    await page.getByLabel('Issuing unit').fill('Phong Dao tao Dai hoc')
    await page
        .getByLabel('Raw bulletin text')
        .fill('Thong bao hoc phi he dao tao chat luong cao co hieu luc tu hoc ky he nam 2026 va da du thong tin de he thong trich xuat.')
    await page.getByRole('checkbox', { name: 'I confirm this source comes from an official UIT or faculty channel.' }).check()
    await page.getByRole('checkbox', { name: 'I understand the document enters a human review queue before it becomes trusted.' }).check()
    await page.getByRole('button', { name: 'Submit for review' }).click()

    await expect(page.getByText('uploading')).toBeVisible()
    await expect(page.getByText('announcement', { exact: false })).toBeVisible()
})

test('operator can open review queue and retry a failed job', async ({ page }) => {
    await setStoredRole(page, 'operator')
    await page.goto('/portal/review')

    await expect(page.getByRole('heading', { name: 'Review queue', level: 1 })).toBeVisible()
    await expect(page.getByText('Reviewer decision workspace')).toBeVisible()
    await page.getByRole('link', { name: 'Open submission detail' }).click()
    await expect(page.getByRole('heading', { name: 'Submission detail', level: 1 })).toBeVisible()

    await page.goto('/portal/jobs?scenario=failed-job')
    await expect(page.getByRole('heading', { name: 'Jobs monitor' })).toBeVisible()
    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByText('Retry accepted for')).toBeVisible()
})
