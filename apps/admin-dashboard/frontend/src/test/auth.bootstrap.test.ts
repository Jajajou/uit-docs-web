import { describe, expect, it } from 'vitest'
import {
    buildAuthCallbackTarget,
    buildInternalSsoStartTarget,
    readAuthError,
    readAuthErrorMessage,
    readBootstrapReturnTo,
    readBootstrapRole,
    resolveSessionRedirectPath,
} from '@/entities/auth/bootstrap'

describe('auth bootstrap helpers', () => {
    it('builds a callback target with encoded return path', () => {
        const target = buildAuthCallbackTarget('admin', '/manager?scenario=error')

        expect(target).toContain('/auth/callback?')
        expect(target).toContain('bootstrap=1')
        expect(target).toContain('role=admin')
        expect(target).toContain('returnTo=%2Fmanager%3Fscenario%3Derror')
    })

    it('reads bootstrap query params safely', () => {
        const params = new URLSearchParams('bootstrap=1&role=teacher&returnTo=%2Fupload')

        expect(readBootstrapRole(params)).toBe('teacher')
        expect(readBootstrapReturnTo(params)).toBe('/upload')
    })

    it('builds the backend-owned SSO start target and reads auth errors safely', () => {
        const target = buildInternalSsoStartTarget('/admin/users')
        const params = new URLSearchParams(
            'returnTo=%2Fportal%2Freview&authError=access_denied&authErrorMessage=Institutional%20login%20failed',
        )

        expect(target).toBe('/api/auth/sso/start?returnTo=%2Fadmin%2Fusers')
        expect(readAuthError(params)).toBe('access_denied')
        expect(readAuthErrorMessage(params)).toBe('Institutional login failed')
    })

    it('falls back to default paths when return target is not allowed', () => {
        expect(resolveSessionRedirectPath('teacher', '/manager')).toBe('/chat')
        expect(resolveSessionRedirectPath('student', '/manager')).toBe('/chat')
        expect(resolveSessionRedirectPath('admin', '/manager')).toBe('/manager')
    })
})
