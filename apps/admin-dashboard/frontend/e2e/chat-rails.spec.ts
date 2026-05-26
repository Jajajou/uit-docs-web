import { expect, test } from '@playwright/test'
import { setStoredRole } from './helpers'

test('desktop chat rails stay fixed and toggle independently', async ({ page }) => {
    await setStoredRole(page, 'student')
    await page.goto('/chat')

    const historyRail = page.getByTestId('chat-history-rail')
    const historyToggle = page.getByTestId('chat-history-rail-toggle')
    const referenceRail = page.getByTestId('chat-reference-rail')
    const referenceToggle = page.getByTestId('chat-reference-rail-toggle')
    const messagesViewport = page.getByTestId('chat-messages-viewport')
    const composerInput = page.getByTestId('chat-composer-input')
    const sendButton = page.getByTestId('chat-composer-send')

    await expect(historyRail).toBeVisible()

    if (!(await referenceRail.isVisible().catch(() => false))) {
        await composerInput.fill('Thong bao hoc phi hien tai con hieu luc khong?')
        await sendButton.click()
        await expect(referenceRail).toBeVisible({ timeout: 15_000 })
    }

    await expect(referenceRail).toBeVisible()
    await expect(historyRail).toHaveCSS('position', 'fixed')
    await expect(referenceRail).toHaveCSS('position', 'fixed')
    await expect(historyRail).toContainText('L\u1ecbch s\u1eed')
    await expect(referenceRail).toContainText('Ngu\u1ed3n')
    await expect(page.locator('body')).not.toContainText(/\\u[0-9a-fA-F]{4}/)

    const historyCollapsed = await historyRail.boundingBox()
    const referenceCollapsed = await referenceRail.boundingBox()

    expect(historyCollapsed).not.toBeNull()
    expect(referenceCollapsed).not.toBeNull()

    await historyToggle.click()
    await page.waitForTimeout(450)

    const historyExpanded = await historyRail.boundingBox()
    expect(historyExpanded).not.toBeNull()
    expect(historyExpanded!.width).toBeGreaterThan(historyCollapsed!.width + 120)
    await expect(historyRail).toContainText('C\u00e1c ch\u1ee7 \u0111\u1ec1 g\u1ea7n \u0111\u00e2y')

    await referenceToggle.click()
    await page.waitForTimeout(450)

    const referenceExpanded = await referenceRail.boundingBox()
    expect(referenceExpanded).not.toBeNull()
    expect(referenceExpanded!.width).toBeGreaterThan(referenceCollapsed!.width + 120)
    await expect(referenceRail).toContainText('Ngu\u1ed3n \u0111ang \u0111\u01b0\u1ee3c tr\u00edch d\u1eabn')

    await messagesViewport.evaluate((element) => {
        element.scrollTop = element.scrollHeight
    })
    await page.waitForTimeout(250)

    const historyAfterScroll = await historyRail.boundingBox()
    const referenceAfterScroll = await referenceRail.boundingBox()

    expect(historyAfterScroll).not.toBeNull()
    expect(referenceAfterScroll).not.toBeNull()
    expect(Math.abs(historyAfterScroll!.y - historyExpanded!.y)).toBeLessThan(2)
    expect(Math.abs(referenceAfterScroll!.y - referenceExpanded!.y)).toBeLessThan(2)

    await historyToggle.click()
    await page.waitForTimeout(450)

    const historyCollapsedAgain = await historyRail.boundingBox()
    const referenceStillExpanded = await referenceRail.boundingBox()

    expect(historyCollapsedAgain).not.toBeNull()
    expect(referenceStillExpanded).not.toBeNull()
    expect(historyCollapsedAgain!.width).toBeLessThan(historyExpanded!.width - 120)
    expect(Math.abs(referenceStillExpanded!.width - referenceExpanded!.width)).toBeLessThan(12)

    await referenceToggle.click()
    await page.waitForTimeout(450)

    const referenceCollapsedAgain = await referenceRail.boundingBox()
    expect(referenceCollapsedAgain).not.toBeNull()
    expect(referenceCollapsedAgain!.width).toBeLessThan(referenceExpanded!.width - 120)
})
