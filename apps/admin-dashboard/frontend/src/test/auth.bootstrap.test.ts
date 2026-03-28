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
        const target = buildAuthCallbackTarget('operator', '/portal/review?scenario=error')

        expect(target).toContain('/auth/callback?')
        expect(target).toContain('bootstrap=1')
        expect(target).toContain('role=operator')
        expect(target).toContain('returnTo=%2Fportal%2Freview%3Fscenario%3Derror')
    })

    it('reads bootstrap query params safely', () => {
        const params = new URLSearchParams('bootstrap=1&role=lecturer&returnTo=%2Fportal%2Fupload')

        expect(readBootstrapRole(params)).toBe('lecturer')
        expect(readBootstrapReturnTo(params)).toBe('/portal/upload')
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
        expect(resolveSessionRedirectPath('lecturer', '/portal/review')).toBe('/portal')
        expect(resolveSessionRedirectPath('guest', '/admin/users')).toBe('/')
        expect(resolveSessionRedirectPath('admin', '/admin/settings')).toBe('/admin/settings')
    })
})
