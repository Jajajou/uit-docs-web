import { expect, type Page } from '@playwright/test'

type SessionRole = 'guest' | 'student' | 'lecturer' | 'operator' | 'admin'

export async function setStoredRole(page: Page, role: SessionRole) {
    await page.addInitScript((selectedRole) => {
        window.localStorage.setItem(
            'uit-docs-agent-session',
            JSON.stringify({
                state: { selectedRole },
                version: 0,
            }),
        )
    }, role)
}

export async function loginAsRole(page: Page, role: Exclude<SessionRole, 'guest'>) {
    await page.goto('/auth/login')
    await expect(page.getByRole('heading', { name: /Session bootstrap|Sign in/i })).toBeVisible()

    const internalSsoButton = page.getByRole('button', { name: 'Continue with internal SSO' })
    if (role === 'lecturer' || role === 'operator' || role === 'admin') {
        let shouldUseInternalSso = false

        try {
            await expect(internalSsoButton).toBeVisible({ timeout: 2000 })
            shouldUseInternalSso = true
        } catch {
            shouldUseInternalSso = false
        }

        if (shouldUseInternalSso) {
            await internalSsoButton.click()
            await expect(page).toHaveURL(/\/api\/auth\/sso\/provider/)
            await page.getByRole('link', { name: new RegExp(`Continue as ${role}`, 'i') }).click()
        } else {
            await page.getByRole('button', { name: new RegExp(`Continue as ${role}`, 'i') }).click()
        }
    } else {
        await page.getByRole('button', { name: new RegExp(`Continue as ${role}`, 'i') }).click()
    }

    if (role === 'lecturer' || role === 'operator') {
        await expect(page).toHaveURL(/\/portal/)
        return
    }

    if (role === 'admin') {
        await expect(page).toHaveURL(/\/admin\/users$/)
        return
    }

    await expect(page).toHaveURL(/\/$/)
}
