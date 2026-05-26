import { expect, type APIRequestContext, type Page } from '@playwright/test'

type SessionRole = 'student' | 'teacher' | 'admin'
type LiveLoginOptions = {
    returnTo?: string
    scenario?: string
}

function getDefaultReturnTo(role: SessionRole) {
    return role === 'admin' ? '/manager' : role === 'teacher' ? '/upload' : '/chat'
}

function serializeLiveRole(role: SessionRole) {
    return role
}

export async function setStoredRole(page: Page, role: SessionRole) {
    await page.addInitScript((selectedRole) => {
        window.localStorage.setItem(
            'uit-docs-agent-session',
            JSON.stringify({
                state: {
                    selectedRole,
                    bootstrapRequest: null,
                },
                version: 0,
            }),
        )
    }, role)
}

export async function loginAsRole(page: Page, role: SessionRole, returnTo?: string) {
    const fallbackReturnTo = getDefaultReturnTo(role)
    const params = new URLSearchParams({
        bootstrap: '1',
        role,
    })

    params.set('returnTo', returnTo ?? fallbackReturnTo)

    await page.goto(`/auth/callback?${params.toString()}`)

    if (role === 'admin') {
        await expect(page).toHaveURL(/\/manager$/)
        return
    }

    if (role === 'teacher') {
        await expect(page).toHaveURL(/\/upload$/)
        return
    }

    await expect(page).toHaveURL(/\/chat$/)
}

export async function resetLiveBackendState(request: APIRequestContext) {
    const response = await request.post('/api/test/reset')
    if (response.status() === 404) {
        return
    }
    expect(response.status()).toBe(204)
}

export async function loginAsLiveRole(page: Page, role: SessionRole, options: LiveLoginOptions = {}) {
    const params = new URLSearchParams()
    if (options.scenario) {
        params.set('scenario', options.scenario)
    }

    let response = await page.request.post(`/api/test/session${params.size > 0 ? `?${params.toString()}` : ''}`, {
        data: {
            role: serializeLiveRole(role),
        },
    })

    if (response.status() === 404) {
        response = await page.request.post(`/api/auth/bootstrap${params.size > 0 ? `?${params.toString()}` : ''}`, {
            data: {
                role: serializeLiveRole(role),
            },
        })
    }

    expect(response.ok()).toBeTruthy()

    const target = options.returnTo ?? getDefaultReturnTo(role)
    await page.goto(target)

    if (role === 'admin') {
        await expect(page).toHaveURL(/\/manager$/)
        return
    }

    if (role === 'teacher') {
        await expect(page).toHaveURL(/\/upload$/)
        return
    }

    await expect(page).toHaveURL(/\/chat$/)
}
